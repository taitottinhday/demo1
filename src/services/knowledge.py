"""Versioned local PDF ingestion, table-aware chunks and BM25 retrieval.

All text is derived from the supplied PDF. No network fetch or invented admissions facts.
"""

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

import pymupdf


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return re.sub(r"\s+", " ", "".join(c for c in value if not unicodedata.combining(c))).strip()


STOP = set("toi em ban cho hoi la cua va co duoc nao nhung mot nam voi xin muon ve tai truong bao nhieu".split())


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

    def ingest(self):
        metadata = self.root / "sources.md"
        files = sorted((self.root / "raw").glob("*.pdf"))
        if not metadata.exists() or not files:
            raise ValueError("Cần data/sources.md và PDF trong data/raw/.")
        source = metadata.read_text(encoding="utf-8-sig")
        match = re.search(r"File tương ứng:\s*(.+)", source)
        named = self.root / match.group(1).strip() if match else None
        if named and named.exists():
            self.pdf = named
        elif len(files) == 1:
            self.pdf = files[0]
        else:
            raise ValueError("Có nhiều PDF: hãy sửa File tương ứng trong sources.md.")
        url = re.search(r"URL chính thức:\s*(https://\S+)", source)
        if not url or not url.group(1).startswith("https://hust.edu.vn/"):
            raise ValueError("MVP này cần nguồn HTTPS thuộc hust.edu.vn.")
        version = hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        document = pymupdf.open(self.pdf)
        if len(document) < 25:
            raise ValueError("Cần PDF đầy đủ; bản scan cũ không được dùng cho MVP này.")
        pages = [p.get_text() for p in document]
        if sum(map(len, pages)) < 10000:
            raise ValueError("PDF scan chưa có lớp chữ; cần OCR và kiểm tra trước khi lập chỉ mục.")
        self.chunks, self.programs = [], []
        self.manifest = {
            "title": "Thông tin tuyển sinh đại học HUST 2026",
            "url": url.group(1),
            "version": version,
            "pages": len(document),
            "scope": "Đại học chính quy, tuyển sinh từ THPT, HUST 2026",
            "status": "Nguồn do nhóm cung cấp; chưa được cán bộ tuyển sinh duyệt",
            "indexed_pages": "2–25; không dùng bảng điểm 2024/2025 hoặc liên thông/VB2",
        }

        def add(title, text, page, end_page=None, kind="text", code=""):
            if not text.strip():
                return
            self.chunks.append(
                {
                    "id": f"chunk-{len(self.chunks) + 1}",
                    "title": title,
                    "text": clean(text),
                    "page": page,
                    "end_page": end_page or page,
                    "kind": kind,
                    "code": code,
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
        self.counters = [Counter(tokens(c["title"] + " " + c["text"])) for c in self.chunks]
        self.df = Counter(t for c in self.counters for t in c)
        self.average = sum(sum(c.values()) for c in self.counters) / len(self.counters)
        output = self.root / "processed"
        output.mkdir(parents=True, exist_ok=True)
        (output / "knowledge.json").write_text(
            json.dumps(
                {"manifest": self.manifest, "chunks": self.chunks, "programs": self.programs},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return self.manifest

    def program_matches(self, question):
        """Return explicit program matches in the question, without using session context."""
        q = normalize(question)
        codes = set(re.findall(r"\b[A-Z]{2,8}\d{0,3}(?:-[A-Z]+)?\b", question.upper()))
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
            return [dict(c, score=100) for c in self.chunks if "Thông báo trúng tuyển:" in c["text"]][:limit]
        if "tsa" in query:
            query += ["dgtd", "tu", "duy"]
        if "ielts" in query:
            query += ["ngoai", "ngu"]
        query_codes = set(re.findall(r"\b[A-Z]{2,8}\d{0,3}(?:-[A-Z]+)?\b", question.upper()))
        program_codes = {p["code"] for p in self.programs}
        selected = (query_codes & program_codes) or ({program} if program in program_codes else set())
        if any(t in norm for t in ["bao nhieu nganh", "so nganh", "bao nhieu chuong trinh"]):
            return [dict(c, score=100) for c in self.chunks if c["kind"] == "overview"]
        fee_query = "hoc phi" in norm
        language_query = any(t in norm for t in ["ngoai ngu", "ielts", "vstep"]) and not any(
            t in norm for t in ["phi", "xac thuc", "quy doi", "diem thuong"]
        )
        if language_query:
            # Language conditions live in section 5.2, not in the program quota table.
            rules = [c for c in self.chunks if c["page"] == 16 and "5.5" in c["text"] and "VSTEP" in c["text"]]
            code = self.resolve_program(question, program)
            rows = [c for c in self.chunks if c["kind"] == "program" and c["code"] == code]
            return [dict(c, score=100) for c in (rules + rows)[:limit]]
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
            if preferred_pages and chunk["page"] in preferred_pages:
                score += 15
            if fee_query and chunk["kind"] != "fee":
                continue
            if fee_query and selected:
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
            if matched and score >= 3:
                scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        # Require lexical support beyond incidental overlap.
        return [dict(c, score=round(s, 2)) for s, c in scored[:limit]]

    def citation(self, chunk):
        return {
            "id": chunk["id"],
            "title": chunk["title"],
            "page": chunk["page"],
            "end_page": chunk["end_page"],
            "url": self.manifest["url"] + f"#page={chunk['page']}",
            "local_url": f"/api/v1/source/pdf#page={chunk['page']}",
            "excerpt": chunk["text"],
            "version": self.manifest["version"][:12],
            "year": 2026,
            "document_title": self.manifest.get("title", "Tài liệu tuyển sinh"),
            "document_status": self.manifest.get("status", ""),
            "indexed_pages": self.manifest.get("indexed_pages", ""),
        }
