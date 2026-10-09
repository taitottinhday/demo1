"""Versioned, source-aware local ingestion and BM25 retrieval for HUST admissions data."""

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import pymupdf


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return re.sub(r"\s+", " ", "".join(c for c in value if not unicodedata.combining(c))).strip()


STOP = set("toi em ban cho hoi la cua va co duoc nao nhung mot nam voi xin muon ve tai truong bao nhieu".split())
PROGRAM_CODE_RE = r"\b[A-Z]{1,8}(?:-[A-Z]{1,3})?\d{0,3}\b"


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", normalize(text)) if t not in STOP]


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


class Knowledge:
    def __init__(self, data_dir: str | Path):
        self.root = Path(data_dir)
        self.chunks = []
        self.programs = []
        self.manifest = {}
        self.pdf = None
        self.documents = []
        self.documents_by_id = {}
        self.primary_source_id = ""
        self.version = ""

    def _source_path(self, source):
        """Resolve a catalog path inside this data directory, never an arbitrary path."""
        local_path = source.get("local_path")
        if not local_path:
            return None
        relative = Path(local_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Đường dẫn nguồn không an toàn: {source.get('id')}")
        if relative.parts and relative.parts[0].casefold() == "data":
            relative = Path(*relative.parts[1:])
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError(f"Đường dẫn nguồn nằm ngoài data/: {source.get('id')}")
        return path

    def source_path(self, source_id=""):
        """Return the local PDF belonging to a known source, or None for web-only sources."""
        source = self.documents_by_id.get(source_id) if source_id else self.documents_by_id.get(self.primary_source_id)
        return self._source_path(source) if source else None

    @staticmethod
    def _split_page(text, max_chars=1500, overlap=180):
        """Split extracted text into page-local chunks with a small context overlap."""
        text = (text or "").strip()
        if not text:
            return []
        pieces = []
        start = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            if end < len(text):
                boundary = max(text.rfind("\n", start + max_chars // 2, end), text.rfind(". ", start + max_chars // 2, end))
                if boundary > start:
                    end = boundary + (1 if text[boundary] == "\n" else 2)
            piece = text[start:end].strip()
            if piece:
                pieces.append(piece)
            if end >= len(text):
                break
            start = max(start + 1, end - overlap)
        return pieces

    def ingest(self):
        metadata = self.root / "sources.md"
        catalog_path = self.root / "source_catalog.json"
        if not metadata.exists() or not catalog_path.exists():
            raise ValueError("Cần data/sources.md và data/source_catalog.json.")
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.documents = catalog.get("documents", [])
        self.documents_by_id = {item.get("id"): item for item in self.documents if item.get("id")}
        if len(self.documents_by_id) != len(self.documents):
            raise ValueError("Danh mục nguồn thiếu ID hoặc có ID trùng.")
        self.primary_source_id = catalog.get("runtime_ingestion", {}).get("source_id", "")
        primary = self.documents_by_id.get(self.primary_source_id)
        if not primary or primary.get("type") != "pdf" or not primary.get("indexable"):
            raise ValueError("Nguồn PDF chính không hợp lệ hoặc chưa thể lập chỉ mục.")
        self.pdf = self._source_path(primary)
        if not self.pdf or not self.pdf.is_file():
            raise ValueError("Không tìm thấy PDF nguồn chính.")

        versions = []
        for item in self.documents:
            path = self._source_path(item)
            if not path:
                continue
            if not path.is_file():
                raise ValueError(f"Thiếu tệp nguồn đã khai báo: {item.get('id')}")
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if item.get("sha256") and actual_hash != item["sha256"].lower():
                raise ValueError(f"Checksum nguồn không khớp catalog: {item.get('id')}")
            item["resolved_path"] = path
            item["version"] = actual_hash
            if item.get("indexable") and item.get("type") == "pdf":
                pdf = pymupdf.open(path)
                if item.get("pages") and len(pdf) != item["pages"]:
                    raise ValueError(f"Số trang PDF không khớp catalog: {item.get('id')}")
                if sum(len(page.get_text()) for page in pdf) < 1000:
                    raise ValueError(f"PDF chưa có đủ lớp văn bản: {item.get('id')}")
                pdf.close()
            versions.append(f"{item['id']}:{actual_hash}")
        facts_path = self.root / "normalized" / "admissions_facts_2026.json"
        if facts_path.exists():
            versions.append("facts:" + hashlib.sha256(facts_path.read_bytes()).hexdigest())
        self.version = hashlib.sha256("\n".join(sorted(versions)).encode("utf-8")).hexdigest()

        document = pymupdf.open(self.pdf)
        if len(document) < 25:
            raise ValueError("Cần PDF đầy đủ; bản scan cũ không được dùng cho MVP này.")
        pages = [p.get_text() for p in document]
        if sum(map(len, pages)) < 10000:
            raise ValueError("PDF scan chưa có lớp chữ; cần OCR và kiểm tra trước khi lập chỉ mục.")
        self.chunks, self.programs = [], []
        self.manifest = {
            "title": primary["title"],
            "url": primary["official_url"],
            "version": self.version,
            "source_id": self.primary_source_id,
            "pages": len(document),
            "scope": catalog.get("corpus_scope", "Tuyển sinh và thông tin đào tạo HUST theo phạm vi từng tài liệu."),
            "status": "Kho nguồn gồm tài liệu chính thức; mỗi câu trả lời cần đối chiếu đúng nguồn và phạm vi áp dụng.",
            "indexed_pages": "2–25; không dùng bảng điểm 2024/2025 hoặc liên thông/VB2",
            "document_count": len(self.documents),
            "indexable_pdf_count": sum(1 for item in self.documents if item.get("type") == "pdf" and item.get("indexable")),
            "unavailable_sources": [
                {"id": item["id"], "title": item.get("title"), "status": item.get("status")}
                for item in self.documents
                if item.get("type") == "pdf" and not item.get("indexable")
            ],
        }

        primary_version = primary["version"]

        def add(
            title,
            text,
            page,
            end_page=None,
            kind="text",
            code="",
            source_id=None,
            excerpt=None,
            answer_vi=None,
            scope_vi=None,
            topic=None,
            fact_id="",
        ):
            if not text.strip():
                return
            source_id = source_id or self.primary_source_id
            source = self.documents_by_id.get(source_id, primary)
            source_path = source.get("resolved_path")
            page_fragment = f"#page={page}" if page else ""
            self.chunks.append(
                {
                    "id": f"chunk-{len(self.chunks) + 1}",
                    "title": title,
                    "text": clean(text),
                    "page": page,
                    "end_page": end_page or page,
                    "kind": kind,
                    "code": code,
                    "topic": topic or "",
                    "fact_id": fact_id,
                    "answer_vi": answer_vi or "",
                    "scope_vi": scope_vi or "",
                    "evidence": clean(excerpt or text),
                    "source_id": source_id,
                    "source_title": source.get("title", "Tài liệu HUST"),
                    "source_url": source.get("official_url", ""),
                    "source_type": source.get("type", "pdf"),
                    "source_version": source.get("version", primary_version),
                    "source_status": source.get("status", ""),
                    "source_local": bool(source_path),
                    "source_scope": source.get("scope", ""),
                }
            )

        # Row reconstruction across page breaks, rather than flattening table columns.
        current = None
        for idx in range(4, 14):
            page = document[idx]
            for table in page.find_tables().tables:
                for row in table.extract():
                    if len(row) != 8:
                        continue
                    cells = [clean(c) for c in row]
                    if cells[0] == "TT" or "Mã xét" in cells[1]:
                        continue
                    if re.fullmatch(r"\d+", cells[0]) and cells[1]:
                        if current:
                            self.programs.append(current)
                        current = {
                            "code": cells[1],
                            "name": cells[2],
                            "major_code": cells[3],
                            "quota": cells[5],
                            "methods": cells[6],
                            "note": cells[7],
                            "page": idx + 1,
                            "end_page": idx + 1,
                        }
                    elif current:
                        for key, pos in [("name", 2), ("methods", 6), ("note", 7)]:
                            if cells[pos] and cells[pos] not in current[key]:
                                current[key] = clean(current[key] + " " + cells[pos])
                        current["end_page"] = idx + 1
        if current:
            self.programs.append(current)
        for item in self.programs:
            text = (
                f"Mã xét tuyển {item['code']}: {item['name']}. Mã ngành {item['major_code']}. "
                f"Chỉ tiêu năm 2026: {item['quota']}. {item['methods']}. {item['note']}"
            )
            add(item["name"], text, item["page"], item["end_page"], "program", item["code"])
        if len(self.programs) < 50:
            raise ValueError("Không đọc đủ bảng ngành. Kiểm tra bố cục PDF trước demo.")
        add(
            "Số ngành và chương trình tuyển sinh 2026",
            f"Theo bảng tuyển sinh 2026, HUST có {len({p['major_code'] for p in self.programs})} mã ngành đào tạo và {len(self.programs)} chương trình/mã xét tuyển. Một ngành có thể có nhiều chương trình; hai số này không đồng nghĩa.",
            5,
            14,
            "overview",
        )

        # Non-table text pages: retain enough adjacent context for conditions and exceptions.
        for idx in [1, 2, 3, 14, 15, 17, 18, 19, 23, 24]:
            text = pages[idx]
            if idx == 19:
                text = text.split("Bảng 3.")[0]
            blocks = re.split(r"(?=\n(?:\d+\.\d*\.? |\([123]\)|[abc]\)|- |• ))", text)
            group = ""
            for block in blocks:
                if len(group) + len(block) > 1700 and group:
                    add(f"Nội dung tuyển sinh — trang PDF {idx + 1}", group, idx + 1)
                    group = group[-250:] + " " + block
                else:
                    group += block
            add(f"Nội dung tuyển sinh — trang PDF {idx + 1}", group, idx + 1)

        # Merged fee cells are resolved with the table's unit, not detached prices.
        for idx in range(19, 23):
            for table in document[idx].find_tables().tables:
                rows = table.extract()
                inherited = "28 - 40" if idx == 20 else ""
                for row in rows:
                    cells = [clean(c) for c in row if c is not None]
                    if not cells or not cells[0].isdigit() or len(cells) < 2:
                        continue
                    # Table geometry may have extra columns; price cells are recognized explicitly.
                    name = cells[1]
                    price = next((c for c in cells[2:] if re.fullmatch(r"[~≈]?\s*\d+(?:\s*[-–]\s*\d+)?", c)), "")
                    if price:
                        inherited = price
                    if not inherited:
                        continue
                    unit = "triệu đồng/năm học" if idx in [19, 20, 21] else "triệu đồng/học kỳ"
                    if idx == 22 and "Tiếng Anh" in name:
                        unit = "triệu đồng/năm"
                    # Elitech headings carry groups; table titles are included for disambiguation.
                    category = (
                        "chương trình chuẩn"
                        if idx in [19, 20]
                        else "Elitech"
                        if idx == 21
                        else "hợp tác quốc tế/tài năng"
                    )
                    add(
                        f"Học phí {name} ({category})",
                        f"Học phí dự kiến K71 năm học 2026–2027, {category}: {name}: {inherited} {unit}. Đây là mức trung bình dự kiến, không phải cam kết học phí cá nhân.",
                        idx + 1,
                        kind="fee",
                    )

        document.close()

        # Index each readable supplemental PDF as page-local text. The primary
        # admissions PDF keeps its table-aware parsing above; scans are excluded
        # by catalog metadata until OCR output has been reviewed.
        for source in self.documents:
            if source.get("id") == self.primary_source_id or source.get("type") != "pdf" or not source.get("indexable"):
                continue
            source_path = source.get("resolved_path")
            if not source_path:
                continue
            supplemental_pdf = pymupdf.open(source_path)
            for page_index, pdf_page in enumerate(supplemental_pdf):
                page_text = pdf_page.get_text()
                for part_index, part in enumerate(self._split_page(page_text), 1):
                    add(
                        f"{source['title']} · PDF trang {page_index + 1}",
                        part,
                        page_index + 1,
                        kind="document_text",
                        source_id=source["id"],
                        excerpt=part,
                    )
            supplemental_pdf.close()

        # Curated, page-verified facts sit alongside raw source chunks. They
        # improve retrieval for exact questions and retain their original quote.
        facts_path = self.root / "normalized" / "admissions_facts_2026.json"
        if facts_path.exists():
            facts = json.loads(facts_path.read_text(encoding="utf-8")).get("facts", [])
            for fact in facts:
                source = self.documents_by_id.get(fact.get("source_id"))
                if not source:
                    raise ValueError(f"Dữ kiện tham chiếu nguồn chưa khai báo: {fact.get('id')}")
                evidence = clean(fact.get("evidence", ""))
                page = fact.get("page")
                source_path = source.get("resolved_path")
                if source.get("type") == "pdf":
                    if not source_path or not source.get("indexable") or not isinstance(page, int):
                        raise ValueError(f"Dữ kiện PDF không có trang nguồn hợp lệ: {fact.get('id')}")
                    source_pdf = pymupdf.open(source_path)
                    if not 1 <= page <= len(source_pdf) or normalize(evidence) not in normalize(source_pdf[page - 1].get_text()):
                        source_pdf.close()
                        raise ValueError(f"Trích dẫn không khớp PDF nguồn: {fact.get('id')}")
                    source_pdf.close()
                elif page is not None or not evidence:
                    raise ValueError(f"Dữ kiện web phải có trích dẫn và không gán số trang PDF: {fact.get('id')}")
                answer = clean(fact.get("claim_vi", ""))
                scope_text = clean(fact.get("scope_vi", ""))
                aliases = " ".join(fact.get("aliases", []))
                text = f"{answer} Phạm vi áp dụng: {scope_text} Trích dẫn nguyên văn: {evidence} {aliases}"
                add(
                    fact.get("topic", "Dữ kiện đã kiểm chứng"),
                    text,
                    page,
                    kind="verified_fact",
                    source_id=fact["source_id"],
                    excerpt=evidence,
                    answer_vi=answer,
                    scope_vi=scope_text,
                    topic=fact.get("topic", ""),
                    fact_id=fact.get("id", ""),
                )

        self.counters = [Counter(tokens(c["title"] + " " + c["text"])) for c in self.chunks]
        self.df = Counter(t for c in self.counters for t in c)
        self.average = sum(sum(c.values()) for c in self.counters) / len(self.counters)
        output = self.root / "processed"
        output.mkdir(parents=True, exist_ok=True)
        (output / "knowledge.json").write_text(
            json.dumps(
                {
                    "manifest": self.manifest,
                    "documents": [
                        {key: value for key, value in item.items() if key != "resolved_path"}
                        for item in self.documents
                    ],
                    "chunks": self.chunks,
                    "programs": self.programs,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return self.manifest

    def program_matches(self, question):
        """Return explicit program matches in the question, without using session context."""
        q = normalize(question)
        codes = set(re.findall(PROGRAM_CODE_RE, question.upper()))
        matches = [p for p in self.programs if p["code"] in codes]
        matched_codes = {p["code"] for p in matches}
        for program in self.programs:
            names = {
                normalize(program["name"].replace("CNTT: ", "")),
                normalize(program["name"].replace("CNTT: ", "").split("(")[0]).strip(),
            }
            if any(
                len(name) >= 5
                and re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", q)
                for name in names
            ) and program["code"] not in matched_codes:
                matches.append(program)
                matched_codes.add(program["code"])
        return matches

    def resolve_program(self, question, context=""):
        explicit = self.program_matches(question)
        if len(explicit) == 1:
            return explicit[0]["code"]
        return context if not explicit else ""

    def search(self, question: str, program: str = "", limit=4):
        query = tokens(question)
        query = list(dict.fromkeys(query))
        norm = normalize(question)
        result_date = any(t in norm for t in ["ket qua", "trung tuyen", "diem chuan"]) and any(
            t in norm for t in ["khi nao", "bao gio", "ngay nao", "thoi gian", "thong bao", "cong bo"]
        )
        if result_date:
            return [
                dict(c, score=100)
                for c in self.chunks
                if c.get("source_id") == self.primary_source_id and "Thông báo trúng tuyển:" in c["text"]
            ][:limit]
        if "tsa" in query:
            query += ["dgtd", "tu", "duy"]
        if "ielts" in query:
            query += ["ngoai", "ngu"]
        query_codes = set(re.findall(PROGRAM_CODE_RE, question.upper()))
        program_codes = {p["code"] for p in self.programs}
        selected = (query_codes & program_codes) or ({program} if program in program_codes else set())
        if any(t in norm for t in ["bao nhieu nganh", "so nganh", "bao nhieu chuong trinh"]):
            return [
                dict(c, score=100)
                for c in self.chunks
                if c["kind"] == "overview" and c.get("source_id") == self.primary_source_id
            ]
        fee_query = "hoc phi" in norm
        per_credit_fee_query = any(term in norm for term in ["tchp", "tin chi", "moi tin chi", "tin hoc phi"])
        postgraduate_fee_query = fee_query and any(term in norm for term in ["thac si", "tien si", "sau dai hoc"])
        language_query = any(t in norm for t in ["ngoai ngu", "tieng anh", "ielts", "vstep", "placement test", "hust ept", "k71"]) and not any(
            t in norm for t in ["phi", "xac thuc", "quy doi", "diem thuong"]
        )
        graduation_language_query = language_query and any(
            term in norm for term in ["dau ra", "tot nghiep", "placement test", "hust ept", "k71"]
        )
        if graduation_language_query:
            placement_test_query = any(term in norm for term in ["placement test", "hust ept"])
            troy_query = "troy" in norm
            k71_query = "k71" in norm
            ranked_facts = []
            for chunk, counts in zip(self.chunks, self.counters, strict=True):
                if chunk["kind"] != "verified_fact" or chunk.get("topic") not in {
                    "english_policy_scope",
                    "english_graduation",
                    "english_program_exception",
                }:
                    continue
                answer_text = normalize(chunk.get("answer_vi", ""))
                if placement_test_query and "placement test" not in answer_text:
                    continue
                if troy_query and "troy" not in normalize(chunk.get("text", "")):
                    continue
                if k71_query and chunk.get("topic") != "english_policy_scope":
                    continue
                if not (placement_test_query or troy_query or k71_query):
                    if chunk.get("topic") != "english_graduation" or "placement test" in answer_text:
                        continue
                matched = sum(1 for token in query if counts[token])
                score = matched * 4.0
                if any(term in norm for term in ["dau ra", "tot nghiep"]) and chunk.get("topic") == "english_graduation":
                    score += 16
                if "k71" in norm and chunk.get("topic") == "english_policy_scope":
                    score += 16
                if matched and score >= 4:
                    ranked_facts.append((score, chunk))
            ranked_facts.sort(key=lambda item: item[0], reverse=True)
            if "dau vao" in norm and program:
                entrance_rules = [
                    chunk for chunk in self.chunks
                    if chunk.get("source_id") == self.primary_source_id
                    and chunk.get("page") == 16
                    and "5.5" in chunk["text"]
                    and "VSTEP" in chunk["text"]
                ]
                program_rows = [
                    chunk for chunk in self.chunks
                    if chunk.get("kind") == "program" and chunk.get("code") == program
                ]
                return [
                    *[dict(chunk, score=100) for chunk in entrance_rules[:1]],
                    *[dict(chunk, score=100) for chunk in program_rows[:1]],
                    *[dict(chunk, score=score) for score, chunk in ranked_facts[:1]],
                ][:limit]
            return [dict(chunk, score=score) for score, chunk in ranked_facts[:limit]]
        if language_query:
            # Language conditions live in section 5.2, not in the program quota table.
            rules = [
                c
                for c in self.chunks
                if c.get("source_id") == self.primary_source_id
                and c["page"] == 16
                and "5.5" in c["text"]
                and "VSTEP" in c["text"]
            ]
            code = self.resolve_program(question, program)
            rows = [c for c in self.chunks if c["kind"] == "program" and c["code"] == code]
            return [dict(c, score=100) for c in (rules + rows)[:limit]]
        cutoff_query = any(term in norm for term in ["diem chuan", "diem trung tuyen", "diem trung"])
        talent_query = "xttn" in norm or "xet tuyen tai nang" in norm or any(term in norm for term in ["1.1", "1.2", "1.3"])
        if cutoff_query:
            cutoff_facts = [
                chunk for chunk in self.chunks
                if chunk["kind"] == "verified_fact" and chunk.get("topic") == "cutoff"
            ]
            known_codes = {
                code
                for chunk in cutoff_facts
                for code in re.findall(r"\b[A-Z]{2,4}(?:-[A-Z]{1,3})?\d{1,3}\b", chunk.get("answer_vi", "").upper())
            }
            asked_codes = set(re.findall(r"\b[A-Z]{2,4}(?:-[A-Z]{1,3})?\d{1,3}\b", question.upper()))
            asked_codes.update(set(selected) & known_codes)
            requested_program = bool(asked_codes or selected)
            if asked_codes:
                chosen = [
                    chunk for chunk in cutoff_facts
                    if any(code in chunk.get("answer_vi", "").upper() for code in asked_codes & known_codes)
                ]
            elif requested_program:
                chosen = []
            elif "thap nhat" in norm:
                chosen = [chunk for chunk in cutoff_facts if chunk.get("fact_id") == "cutoff-lowest-2026-thpt"]
            elif any(term in norm for term in ["cao nhat", "cao nhì", "cao nhi", "cao nhat la"]):
                chosen = [chunk for chunk in cutoff_facts if chunk.get("fact_id") == "cutoff-it-e10-2026-thpt"]
            else:
                chosen = [chunk for chunk in cutoff_facts if chunk.get("fact_id") == "cutoff-range-2026-thpt"]
            return [dict(chunk, score=100) for chunk in chosen[:limit]]
        if "phuong thuc" in norm and not selected and not talent_query:
            methods = [
                chunk for chunk in self.chunks
                if chunk.get("source_id") == self.primary_source_id
                and chunk.get("page") == 2
            ]
            if methods:
                return [dict(chunk, score=100) for chunk in methods[:limit]]
        preferred_pages = set()
        if "le phi" in norm or "phi thi" in norm or "phi dang ky" in norm or "phi xac thuc" in norm:
            preferred_pages = {20}
        elif "ngoai ngu" in norm or "ielts" in norm or "vstep" in norm:
            preferred_pages = {16}
        elif "k01" in norm:
            preferred_pages = {4, 15, 19}
        elif "dang ky" in norm or "ho so" in norm:
            preferred_pages = {18, 19, 24}
        elif "phuong thuc" in norm and not selected:
            preferred_pages = {2}
        elif "ma truong" in norm or "dia chi" in norm or "lien he" in norm:
            preferred_pages = {2}
        scored = []
        for chunk, counts in zip(self.chunks, self.counters, strict=True):
            length = sum(counts.values())
            if chunk["kind"] == "overview":
                continue
            if chunk["kind"] == "verified_fact" and not (talent_query or per_credit_fee_query or postgraduate_fee_query):
                continue
            if cutoff_query and (chunk["kind"] != "verified_fact" or chunk.get("topic") != "cutoff"):
                continue
            if talent_query and (
                chunk["kind"] != "verified_fact" or chunk.get("topic") != "talent_admission"
            ):
                continue
            if "1.3" in norm and ("dieu kien" in norm or "can gi" in norm):
                answer_text = normalize(chunk.get("answer_vi", ""))
                if "1.3" not in answer_text or not any(term in answer_text for term in ["yeu cau", "dieu kien"]):
                    continue
            if postgraduate_fee_query and (
                chunk["kind"] != "verified_fact"
                or chunk.get("topic") != "tuition"
                or "sau dai hoc" not in normalize(chunk.get("scope_vi", ""))
            ):
                continue
            if fee_query and per_credit_fee_query and (
                chunk["kind"] != "verified_fact" or chunk.get("source_id") != "hust-tuition-2026-2027"
            ):
                continue
            if fee_query and not per_credit_fee_query and not postgraduate_fee_query and chunk["kind"] != "fee":
                continue
            if (
                not selected
                and chunk["kind"] == "program"
                and not any(
                    normalize(p["name"].replace("CNTT: ", "").split("(")[0]).strip() in norm
                    for p in self.programs
                    if p["code"] == chunk["code"]
                )
            ):
                continue
            if not fee_query and chunk["kind"] == "fee":
                continue
            if selected and chunk["kind"] == "verified_fact":
                code_terms = {normalize(code) for code in selected}
                fact_text = normalize(chunk["text"])
                if query_codes and not any(re.search(r"(?<!\w)" + re.escape(code) + r"(?!\w)", fact_text) for code in code_terms):
                    continue
            score = 0.0
            matched = 0
            for token in query:
                tf = counts[token]
                if tf:
                    matched += 1
                    idf = math.log(1 + (len(self.chunks) - self.df[token] + 0.5) / (self.df[token] + 0.5))
                    score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / self.average))
            if selected and chunk["kind"] == "program":
                if chunk["code"] not in selected:
                    continue
                if not fee_query and not preferred_pages:
                    score += 20
            if preferred_pages and chunk.get("source_id") == self.primary_source_id and chunk["page"] in preferred_pages:
                score += 15
            if fee_query and not per_credit_fee_query and not postgraduate_fee_query and chunk["kind"] != "fee":
                continue
            if fee_query and selected and chunk["kind"] == "fee":
                aliases = {
                    "IT1": "Khoa học máy tính",
                    "IT2": "Kỹ thuật máy tính",
                    "ITE7": "Công nghệ thông tin Global ICT",
                    "ITE6": "Công nghệ thông tin Việt Nhật",
                    "ITEP": "Công nghệ thông tin Việt Pháp",
                }
                names = [
                    aliases.get(p["code"], p["name"].replace("CNTT: ", ""))
                    for p in self.programs
                    if p["code"] in selected
                ]
                if not any(
                    normalize(n.split("(")[0]).strip().replace(" - ", " ")
                    in normalize(chunk["title"]).replace(" - ", " ")
                    for n in names
                ):
                    continue
                # Avoid standard vs advanced ambiguity: ask/choose correct table grouping.
                advanced = any(
                    "tiên tiến" in p["name"] or "Global" in p["name"] for p in self.programs if p["code"] in selected
                )
                if advanced and "chuong trinh chuan" in normalize(chunk["title"]):
                    continue
                standard = any(
                    re.fullmatch(r"[A-Z]{2}\d", p["code"]) and p["code"] != "FL2"
                    for p in self.programs
                    if p["code"] in selected
                )
                if standard and "chuong trinh chuan" not in normalize(chunk["title"]):
                    continue
                score += 15
            if chunk["kind"] == "verified_fact":
                score += 9
                if chunk.get("source_id") in {"hust-admission-regulation-2026", "hust-talent-admission-2026", "hust-tuition-2026-2027"}:
                    score += 2
                if cutoff_query and chunk.get("topic") == "cutoff":
                    score += 12
            if matched and score >= 3:
                scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        # Require lexical support beyond incidental overlap.
        return [dict(c, score=round(s, 2)) for s, c in scored[:limit]]

    def citation(self, chunk):
        source_id = chunk.get("source_id", self.primary_source_id)
        source_url = chunk.get("source_url") or self.manifest["url"]
        page = chunk.get("page")
        end_page = chunk.get("end_page") or page
        if chunk.get("source_type", "pdf") == "pdf" and page:
            source_url = f"{source_url}#page={page}"
        local_url = None
        if chunk.get("source_local", True):
            local_url = f"/api/v1/source/pdf?source_id={source_id}"
            if page:
                local_url += f"#page={page}"
        status_labels = {
            "primary_runtime_source": "Nguồn chính của kỳ tuyển sinh 2026.",
            "supplemental_data_only": "Tài liệu chính thức bổ trợ; áp dụng theo phạm vi ghi trong tài liệu.",
            "online_summary_only": "Dữ kiện tóm tắt đối chiếu trang chính thức; chưa bao gồm toàn bộ bảng điểm.",
            "manual_ocr_required": "PDF scan chưa được kiểm tra OCR; không dùng làm căn cứ trả lời.",
            "online_listing_only": "Trang danh mục trực tuyến; chưa có nội dung chi tiết của từng học bổng trong kho.",
        }
        source = self.documents_by_id.get(source_id, {})
        doc_status = status_labels.get(chunk.get("source_status", ""), chunk.get("source_status", ""))
        return {
            "id": chunk["id"],
            "title": chunk.get("source_title", self.manifest.get("title", "Tài liệu tuyển sinh")),
            "section": chunk.get("title", ""),
            "page": page,
            "end_page": end_page,
            "url": source_url,
            "local_url": local_url,
            "excerpt": chunk.get("evidence") or chunk["text"],
            "version": chunk.get("source_version", self.version)[:12],
            "year": 2026,
            "document_title": chunk.get("source_title", self.manifest.get("title", "Tài liệu tuyển sinh")),
            "document_status": doc_status,
            "source_id": source_id,
            "source_type": chunk.get("source_type", "pdf"),
            "scope": chunk.get("source_scope", source.get("scope", "")),
            "indexed_pages": self.manifest.get("indexed_pages", "") if source_id == self.primary_source_id else "",
        }
