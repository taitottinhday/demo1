"""Build a source-traceable K71 data release; never imports or changes the backend.

Usage: python -X utf8 scripts/normalize_admissions_data.py [--skip-ocr]
OCR: tesserocr + Pillow and data/tools/tessdata/{vie,eng}.traineddata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
VERSION = "k71-2026-v1"
PARSER = "admissions-normalizer-1.0"
TITLES = {
    "admissions": "Thông tin tuyển sinh đại học năm 2026",
    "language": "Quy định ngoại ngữ từ K71",
    "tuition": "Quyết định học phí năm học 2026–2027",
    "regulations": "Quy chế tuyển sinh đại học",
    "talent": "Quy định phương thức xét tuyển tài năng từ năm 2026",
    "tsa": "Quy chế thi Đánh giá tư duy",
}
TOPICS = {
    "programs": ["chương trình đào tạo", "mã xét tuyển", "chỉ tiêu"],
    "tuition_rules": ["học phí", "tchp", "tín chỉ học phí"],
    "cutoffs": ["điểm trúng tuyển", "điểm chuẩn"],
    "language_rules": ["ngoại ngữ", "tiếng anh", "ielts", "vstep", "tiếng nhật", "tiếng pháp", "tiếng đức"],
    "scholarships": ["học bổng"],
    "application_steps": ["đăng ký", "nộp hồ sơ"],
    "enrollment_rules": ["xác nhận nhập học", "bảo lưu", "đợt bổ sung", "đợt tiếp theo"],
    "scoring_rules": [
        "tính điểm",
        "quy đổi",
        "điểm thưởng",
        "điểm ưu tiên",
        "chính sách ưu tiên",
        "tiêu chí phụ",
        "tổ hợp",
    ],
    "training_models": ["mô hình", "liên kết đào tạo", "song bằng", "elitech", "cử nhân", "kỹ sư"],
    "contacts": ["điện thoại", "email", "thông tin, hỗ trợ", "địa chỉ", "website"],
    "exam_rules": ["thi đánh giá tư duy", "phúc khảo", "phòng thi", "dự thi", "kỷ luật", "thi trên máy tính"],
    "admission_rules": ["điều kiện", "đối tượng", "xét tuyển", "phỏng vấn"],
    "student_support": ["miễn giảm", "hỗ trợ", "khiếu nại", "quyền", "trách nhiệm"],
}
ISSUES: list[dict] = []


def compact(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value or "")).strip()


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_lines(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def issue(kind, source_id, page, detail):
    ISSUES.append(
        {
            "issue_id": digest(f"{kind}:{source_id}:{page}:{detail}"),
            "kind": kind,
            "source_id": source_id,
            "page": page,
            "detail": detail,
        }
    )


def source_kind(filename):
    if filename.startswith("00_"):
        return "language"
    if filename.startswith("12006"):
        return "tuition"
    if filename.startswith("4740"):
        return "regulations"
    if filename.startswith("qui-dinh"):
        return "talent"
    if filename.startswith("quy-che"):
        return "tsa"
    return "admissions"


def sources():
    content = (DATA / "sources.md").read_text(encoding="utf-8-sig")
    result = []
    for path in sorted((DATA / "raw").glob("*.pdf")):
        kind = source_kind(path.name)
        entries = re.split(r"(?=Tên tài liệu:)", content)
        matched = next((part for part in entries if "raw/" + path.name in part), "")
        url = re.search(r"URL chính thức:\s*(https://\S+)", matched)
        url = url.group(1) if url else None
        canonical = urlunsplit((*urlsplit(url)[:3], "", "")) if url else None
        result.append(
            {
                "source_id": f"hust-{kind}-k71",
                "kind": kind,
                "title": TITLES[kind],
                "local_path": path.relative_to(DATA).as_posix(),
                "url_original": url,
                "url": canonical,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "cohort": "K71",
                "admission_year": 2026,
                "applicability_status": "confirmed_by_project_owner",
                "applicability_note": "Người dùng xác nhận bộ nguồn có hiệu lực cho K71 nhập học 2026; giữ nguyên phạm vi và ngoại lệ từng mục.",
                "content_review_status": "not_staff_reviewed",
                "parser_version": PARSER,
                "academic_year": "2026-2027" if kind in {"tuition", "language"} else None,
                "effective_date": None,
                "publication_date": None,
            }
        )
    # Dates grounded in readable text; remain distinct from the cohort confirmation.
    for item in result:
        if item["kind"] == "language":
            item["publication_date"] = "2026-09-07"
            item["effective_note"] = (
                "Điều 7, trang PDF 5: từ học kỳ 1 năm học 2026–2027; ngoại lệ quy đổi chứng chỉ cho khóa khác."
            )
            issue(
                "metadata_discrepancy",
                item["source_id"],
                5,
                "sources.md ghi 2025-2026; Điều 7 PDF ghi 2026-2027. Manifest dùng nội dung PDF; không sửa sources.md đang được người dùng chỉnh.",
            )
        if item["kind"] == "talent":
            item["publication_date"] = "2026-03-17"
            item["effective_date"] = "2026-03-17"
    # Web URLs are registered as gaps, not silently represented as downloaded evidence.
    web = []
    for part in re.split(r"(?=Tên tài liệu:)", content):
        if "Tên tài liệu:" not in part or "File tương ứng:" in part:
            continue
        match = re.search(r"URL chính thức:\s*(https://\S+)", part)
        if match and not any(row["url"] == match.group(1) for row in web):
            web.append(
                {
                    "url": match.group(1),
                    "status": "not_in_local_raw",
                    "title": compact(part.splitlines()[0].split(":", 1)[1]),
                }
            )
    return result, web


def get_ocr_api(skip):
    if skip:
        return None
    try:
        from tesserocr import PyTessBaseAPI

        return PyTessBaseAPI(path=str(DATA / "tools" / "tessdata"), lang="vie+eng")
    except (ImportError, RuntimeError) as exc:
        raise RuntimeError(
            "OCR chưa sẵn sàng. Cài tesserocr, Pillow và chạy scripts/setup_data_ocr.py; --skip-ocr chỉ tạo bản thiếu OCR."
        ) from exc


def extract(source, api):
    document = pymupdf.open(DATA / source["local_path"])
    pages, tables = [], []
    source["page_count"] = len(document)
    for index, page in enumerate(document):
        number = index + 1
        native = page.get_text(sort=True)
        path = DATA / "extracted" / source["source_id"]
        path.mkdir(parents=True, exist_ok=True)
        needs_ocr = len(native.strip()) < 100 and bool(page.get_images())
        method, confidence, text, words = "native", None, native, []
        if needs_ocr:
            cache = path / f"page-{number:03d}.ocr.json"
            if cache.exists():
                previous = json.loads(cache.read_text(encoding="utf-8"))
                if previous.get("source_version") == source["sha256"]:
                    text, confidence, words = previous["text"], previous["confidence"], previous.get("words", [])
                    method = "ocr"
            if method != "ocr" and api:
                from PIL import Image

                pix = page.get_pixmap(matrix=pymupdf.Matrix(3, 3), alpha=False)
                api.SetImage(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
                api.SetPageSegMode(3)
                recognized = api.GetUTF8Text()
                confidence = api.MeanTextConf()
                iterator = api.GetIterator()
                if iterator:
                    from tesserocr import RIL

                    while True:
                        word = iterator.GetUTF8Text(RIL.WORD)
                        box = iterator.BoundingBox(RIL.WORD)
                        if word and box:
                            words.append(
                                {
                                    "text": word.strip(),
                                    "bbox": [round(x / 3, 2) for x in box],
                                    "confidence": round(iterator.Confidence(RIL.WORD), 2),
                                }
                            )
                        if not iterator.Next(RIL.WORD):
                            break
                text = recognized if not native.strip() else native + "\n" + recognized
                method = "ocr"
                save_json(
                    cache,
                    {
                        "source_version": source["sha256"],
                        "text": text,
                        "confidence": confidence,
                        "words": words,
                        "engine": "tesserocr/vie+eng",
                        "scale": 3,
                    },
                )
            issue(
                "ocr_requires_visual_review" if method == "ocr" else "ocr_missing",
                source["source_id"],
                number,
                f"OCR confidence={confidence}; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.",
            )
        page_tables = []
        if method == "native":
            for ti, table in enumerate(page.find_tables().tables, 1):
                row = {
                    "table_id": f"{source['source_id']}-{source['sha256'][:12]}-p{number}-t{ti}",
                    "source_id": source["source_id"],
                    "source_version": source["sha256"],
                    "page": number,
                    "bbox": list(table.bbox),
                    "rows": [[compact(c) if c is not None else None for c in r] for r in table.extract()],
                    "cells": [list(c) if c else None for c in table.cells],
                    "row_count": table.row_count,
                    "column_count": table.col_count,
                    "review_status": "needs_table_review",
                }
                tables.append(row)
                page_tables.append(row)
        blocks = []
        if method == "native":
            for block in page.get_text("blocks", sort=True):
                if block[6] != 0:
                    continue
                box = pymupdf.Rect(block[:4])
                # Exclude only blocks wholly inside tables; never discard surrounding footnotes.
                if any(pymupdf.Rect(t["bbox"]).contains(box) for t in page_tables):
                    continue
                blocks.append({"bbox": list(block[:4]), "text": block[4]})
        else:
            blocks = [{"bbox": None, "text": text}]
        row = {
            "page_id": f"{source['source_id']}-p{number}",
            "source_id": source["source_id"],
            "source_version": source["sha256"],
            "page": number,
            "printed_page": None,
            "native_text": native,
            "text": unicodedata.normalize("NFC", text),
            "method": method,
            "ocr_confidence": confidence,
            "blocks": blocks,
            "table_ids": [t["table_id"] for t in page_tables],
            "image_count": len(page.get_images()),
            "text_characters": len(text),
        }
        pages.append(row)
        save_json(path / f"page-{number:03d}.json", row)
        (path / f"page-{number:03d}.txt").write_text(row["text"], encoding="utf-8")
        print(f"{source['kind']}: page {number}/{len(document)} ({method})", flush=True)
    document.close()
    save_lines(DATA / "extracted" / source["source_id"] / "tables.jsonl", tables)
    return pages, tables


def classify(text, source_kind):
    value = text.lower()
    tags = [topic for topic, keys in TOPICS.items() if any(key in value for key in keys)]
    if source_kind == "tsa":
        tags = list(dict.fromkeys(["exam_rules"] + tags))
    if source_kind == "language":
        tags = list(dict.fromkeys(["language_rules"] + tags))
    if source_kind == "tuition":
        tags = list(dict.fromkeys(["tuition_rules"] + tags))
    return tags or ["institutional_rules"]


def context(source, page, text):
    kind = source["kind"]
    historical = kind == "admissions" and (28 <= page <= 39 or page >= 46)
    if kind == "admissions" and page >= 40:
        scope = "continuing_or_second_degree"
    elif kind == "regulations" and page >= 14:
        scope = "mixed_or_other_admissions"
    elif kind == "tuition" and page in (5, 6, 7):
        scope = "mixed_training_levels"
    else:
        scope = "undergraduate_regular"
    return {
        "cohort": "K71",
        "admission_year": None if historical else 2026,
        "academic_year": source["academic_year"],
        "scope": scope,
        "audience": "student" if kind == "language" else "applicant_or_student",
        "historical": historical,
        "reference_years": [2024, 2025] if historical else [],
        "mentioned_years": sorted({int(y) for y in re.findall(r"\b20\d{2}\b", text)}),
        "program_codes": sorted(set(re.findall(r"\b(?:[A-Z]{2,5}\d{1,3}(?:-[A-Z]+)?|TROY-IT|ITEP)\b", text))),
    }


def base_record(source, page_start, page_end, text, title, kind="section", location=None):
    position = json.dumps(location, sort_keys=True, ensure_ascii=False)
    record_id = (
        f"{source['source_id']}-{source['sha256'][:12]}-{digest(f'{page_start}:{page_end}:{title}:{text}:{position}')}"
    )
    return {
        "record_id": record_id,
        "record_type": kind,
        "title": title,
        "text": text,
        "source_id": source["source_id"],
        "source_version": source["sha256"],
        "page_start": page_start,
        "page_end": page_end,
        "section_path": [title],
        "topics": classify(title + " " + text, source["kind"]),
        **context(source, page_start, text),
        "review_status": "machine_extracted",
        "evidence": {
            "url": (source["url"] + f"#page={page_start}") if source["url"] else None,
            "local_path": source["local_path"],
            "page_start": page_start,
            "page_end": page_end,
            "location": location,
            "quote": text,
        },
        "applicability_status": "confirmed_by_project_owner",
        "staff_reviewed": False,
    }


def make_sections(source, pages):
    # Split major sections/articles, carry a section across page boundaries. Tables are separate.
    heading = re.compile(
        r"^(?:Điều\s+\d+\.|\d{1,2}\.\d+\.?\s|\d{1,2}\.\s+[A-ZĐÀÁÂĂÊÔƠƯ]|Phụ lục\s+[IVX]+|[IVX]+\.\s+[A-ZĐ])"
    )
    records, current, title, start, end = [], [], source["title"], 1, 1

    def flush():
        if current:
            text = "\n".join(current).strip()
            if len(text) >= 30:
                records.append(base_record(source, start, end, text, title))

    for page in pages:
        number = page["page"]
        # TOC is preserved in extracted pages but excluded from answer evidence.
        if source["kind"] == "regulations" and number == 3:
            issue(
                "toc_excluded",
                source["source_id"],
                number,
                "Mục lục lưu trong extracted, không làm bằng chứng trả lời.",
            )
            continue
        # Narrative records end at page boundary for mixed scopes and historical tables.
        boundary = context(source, number, "")
        previous = context(source, start, "")
        if current and (boundary["scope"], boundary["historical"]) != (previous["scope"], previous["historical"]):
            flush()
            current = []
            title = source["title"]
            start = number
        for block in page["blocks"]:
            for line in block["text"].splitlines():
                line = compact(line)
                if not line or re.fullmatch(r"\d{1,3}", line):
                    continue
                if re.search(r"\.{5,}", line):
                    continue
                if heading.match(line) and len(line) >= 12:
                    flush()
                    current = []
                    title = line
                    start = number
                elif not current:
                    start = number
                current.append(line)
                end = number
    flush()
    return records


def make_table_records(source, tables):
    records = []
    for table in tables:
        # Keep nulls: they express merged/empty cells and must not be forward-filled blindly.
        text = "\n".join(" | ".join(c if c is not None else "[ô gộp/trống]" for c in row) for row in table["rows"])
        title = f"{source['title']} — bảng trang PDF {table['page']}"
        record = base_record(
            source,
            table["page"],
            table["page"],
            text,
            title,
            "table",
            {"table_id": table["table_id"], "bbox": table["bbox"]},
        )
        record.update(
            table_id=table["table_id"],
            rows=table["rows"],
            column_count=table["column_count"],
            review_status="needs_table_review",
            answer_eligible=False,
        )
        records.append(record)
    return records


def semantic_table_rows(source, tables):
    """Serialize labelled table rows, without silently filling merged price cells."""
    records = []
    current_code = None
    for table in tables:
        rows, page = table["rows"], table["page"]
        headers = [compact(c) or f"column_{i + 1}" for i, c in enumerate(rows[0])] if rows else []
        historical = source["kind"] == "admissions" and 28 <= page <= 39 and len(headers) == 18
        for ri, cells in enumerate(rows[1:], 1):
            # Dedicated program reconstruction handles multiline rows.
            if source["kind"] == "admissions" and 5 <= page <= 14:
                continue
            if not any(cells):
                continue
            if historical:
                if cells[0] and cells[1] and re.fullmatch(r"\d+", cells[0]):
                    current_code = cells[1]
                method = compact(cells[7])
                if not current_code or method not in {"XTTN", "DGTD", "ĐGTD", "THPT"}:
                    continue
                for year, pos in [(2025, 11), (2024, 16)]:
                    score = compact(cells[pos])
                    match = re.fullmatch(r"(\d+(?:[.,]\d+)?)/(\d+(?:[.,]\d+)?)", score)
                    if not match:
                        issue(
                            "cutoff_cell_unparsed",
                            source["source_id"],
                            page,
                            f"{current_code}/{method}/{year}: {score!r}",
                        )
                        continue
                    text = f"Điểm trúng tuyển lịch sử {year}, mã {current_code}, phương thức {method}: {score}. Đây không phải điểm chuẩn 2026."
                    record = base_record(
                        source,
                        page,
                        page,
                        text,
                        f"Điểm trúng tuyển {current_code} {year} {method}",
                        "cutoff",
                        {"table_id": table["table_id"], "row_index": ri, "column_index": pos},
                    )
                    record.update(
                        topics=["cutoffs"],
                        program_codes=[current_code],
                        cutoff_year=year,
                        admission_year=year,
                        reference_years=[year],
                        historical=True,
                        score=float(match[1].replace(",", ".")),
                        scale=float(match[2].replace(",", ".")),
                        method=method,
                        review_status="table_reconstructed",
                        answer_eligible=True,
                    )
                    record["evidence"]["quote"] = score
                    records.append(record)
                continue
            # Only compact labelled tables get semantic row serialization. Complex grids remain in tables.jsonl.
            if len(headers) > 7 or not cells[0]:
                continue
            populated = [(headers[i], value) for i, value in enumerate(cells) if value is not None and value != ""]
            if not populated:
                continue
            text = "; ".join(f"{header}: {value}" for header, value in populated)
            title = f"{source['title']} — {compact(cells[0])}"
            record = base_record(
                source, page, page, text, title, "table_row", {"table_id": table["table_id"], "row_index": ri}
            )
            complete = all(value is not None for value in cells)
            record.update(
                columns=[{"name": headers[i], "value": value} for i, value in enumerate(cells)],
                review_status="table_reconstructed" if complete else "needs_table_review",
                answer_eligible=complete,
                unresolved_merged_cells=not complete,
            )
            if source["kind"] == "tuition":
                record["topics"] = ["tuition_rules"]
                record["academic_year"] = "2026-2027"
                if page == 7:
                    table_number = int(table["table_id"].rsplit("-t", 1)[1])
                    record["scope"] = {1: "undergraduate_regular", 2: "continuing_education", 3: "postgraduate"}.get(
                        table_number, "mixed_training_levels"
                    )
                    record["text"] = text + " (Quy đổi TCHT sang TCHP, theo loại học phần và hệ đào tạo.)"
                else:
                    record.update(
                        currency="VND",
                        unit="TCHP",
                        amount_vnd=None,
                        amount_text=compact(cells[-1]),
                        fee_status="decision_rate",
                    )
                    if len(cells) == 2 and re.fullmatch(r"\d+", compact(cells[1])):
                        record["amount_vnd"] = int(cells[1]) * 1000
                        record["text"] = (
                            f"{text}. Đơn vị bảng: nghìn đồng trên một tín chỉ học phí (TCHP), năm học 2026–2027."
                        )
                    else:
                        record["text"] = text + ". Đơn vị bảng: nghìn đồng/TCHP; ô gộp chưa được kế thừa tự động."
                    record["scope"] = "continuing_education" if page == 5 else "undergraduate_regular"
            record["evidence"]["quote"] = " | ".join(value for value in cells if value)
            records.append(record)
    return records


def make_programs(source, tables):
    result, current = [], None
    for table in tables:
        if not 5 <= table["page"] <= 14 or table["column_count"] != 8:
            continue
        for index, row in enumerate(table["rows"]):
            cells = [compact(c) for c in row]
            if re.fullmatch(r"\d+", cells[0]) and re.fullmatch(r"[A-Z][A-Z0-9-]+", cells[1]):
                if current:
                    result.append(current)
                current = {
                    "program_code": cells[1],
                    "program_name": cells[2],
                    "major_code": cells[3],
                    "major_name": cells[4],
                    "quota_text": cells[5],
                    "methods_text": cells[6],
                    "notes": cells[7],
                    "page_start": table["page"],
                    "page_end": table["page"],
                    "table_rows": [{"table_id": table["table_id"], "row_index": index}],
                }
            elif current and (not cells[0] or not cells[0].isdigit()) and cells[0] != "TT" and "Mã xét" not in cells[1]:
                for field, pos in [("program_name", 2), ("methods_text", 6), ("notes", 7)]:
                    if cells[pos] and cells[pos] not in current[field]:
                        current[field] = compact(current[field] + " " + cells[pos])
                current["page_end"] = table["page"]
                current["table_rows"].append({"table_id": table["table_id"], "row_index": index})
    if current:
        result.append(current)
    records = []
    for program in result:
        text = (
            f"Mã xét tuyển {program['program_code']}: {program['program_name']}. "
            f"Mã ngành: {program['major_code']}; tên ngành: {program['major_name']}. "
            f"Chỉ tiêu tuyển sinh 2026: {program['quota_text']}. "
            f"Phương thức: {program['methods_text']}. Ghi chú: {program['notes'] or 'Không có ghi chú riêng trong dòng bảng.'}"
        )
        record = base_record(
            source,
            program["page_start"],
            program["page_end"],
            text,
            program["program_name"],
            "program",
            {"table_rows": program["table_rows"]},
        )
        record.update(program)
        table_lookup = {table["table_id"]: table for table in tables}
        record["evidence"]["quote"] = "\n".join(
            " | ".join(c for c in table_lookup[ref["table_id"]]["rows"][ref["row_index"]] if c)
            for ref in program["table_rows"]
        )
        record.update(
            program_codes=[program["program_code"]],
            topics=["programs", "admission_rules"],
            quota=int(program["quota_text"]) if program["quota_text"].isdigit() else None,
            methods=[key for key in ("XTTN", "ĐGTD", "THPT") if key in program["methods_text"]],
            subject_combinations=sorted(set(re.findall(r"\b[A-DK]\d{2}\b", program["methods_text"]))),
            aliases=[program["program_name"], program["program_name"].replace("CNTT: ", "")],
            teaching_language="English" if "bằng tiếng Anh" in program["notes"] else None,
            review_status="table_reconstructed",
            answer_eligible=True,
        )
        records.append(record)
    if len(records) != 68:
        issue(
            "program_count_check",
            source["source_id"],
            None,
            f"Trích được {len(records)} chương trình; đối chiếu bảng nguồn.",
        )
    return records


def chunks_for(record):
    # Raw table grids are review material, not misleading flattened answer passages.
    if record["record_type"] == "table":
        return []
    sentences = re.split(r"(?<=[.;:])\s+|\n+", record["text"])
    groups, current, size = [], [], 0
    for sentence in sentences:
        words = sentence.split()
        # Bound long OCR lines without dropping any words.
        parts = [" ".join(words[i : i + 400]) for i in range(0, len(words), 400)] or [sentence]
        for part in parts:
            count = len(part.split())
            if current and size + count > 450:
                groups.append("\n".join(current))
                current = []
                size = 0
            current.append(part)
            size += count
    if current:
        groups.append("\n".join(current))
    chunks = []
    for index, text in enumerate(groups, 1):
        item = {
            key: record[key]
            for key in [
                "source_id",
                "source_version",
                "title",
                "page_start",
                "page_end",
                "section_path",
                "topics",
                "cohort",
                "admission_year",
                "academic_year",
                "scope",
                "audience",
                "historical",
                "reference_years",
                "program_codes",
                "review_status",
                "staff_reviewed",
            ]
        }
        item.update(
            chunk_id=f"{record['record_id']}-c{index}-{digest(text)[:8]}",
            record_id=record["record_id"],
            parent_id=record["record_id"],
            text=text,
            retrieval_text=record["title"] + "\n" + text,
            search_text=unicodedata.normalize("NFC", text).casefold(),
            evidence=record["evidence"],
            answer_eligible=record.get("answer_eligible", True),
            context_required=len(groups) > 1 or bool(record.get("related_context_record_ids")),
            related_context_record_ids=record.get("related_context_record_ids", []),
            extraction_method=record.get("extraction_method", "native"),
        )
        chunks.append(item)
    return chunks


def build(skip_ocr=False):
    manifests, web = sources()
    api = get_ocr_api(skip_ocr)
    records, pages, tables = [], [], []
    for source in manifests:
        extracted, grids = extract(source, api)
        sections = make_sections(source, extracted)
        ocr_pages = {p["page"] for p in extracted if p["method"] == "ocr"}
        for record in sections:
            ocr = bool(set(range(record["page_start"], record["page_end"] + 1)) & ocr_pages)
            record["extraction_method"] = "ocr" if ocr else "native"
            record["answer_eligible"] = not ocr
            if ocr:
                record["review_status"] = "needs_ocr_review"
        records.extend(sections)
        records.extend(make_table_records(source, grids))
        records.extend(semantic_table_rows(source, grids))
        if source["kind"] == "admissions":
            records.extend(make_programs(source, grids))
        pages.extend(extracted)
        tables.extend(grids)
    if api:
        api.End()
    # A row alone may omit table units/footnotes: carry links to surrounding prose.
    for record in records:
        if record["record_type"] in {"program", "cutoff", "table_row"}:
            record["related_context_record_ids"] = [
                section["record_id"]
                for section in records
                if section["record_type"] == "section"
                and section["source_id"] == record["source_id"]
                and section["page_start"] <= record["page_end"] + 1
                and section["page_end"] >= record["page_start"] - 1
                and section["scope"] == record["scope"]
                and section["historical"] == record["historical"]
            ]
    chunks = [chunk for record in records for chunk in chunks_for(record)]
    save_json(DATA / "manifests" / "sources.json", {"release": VERSION, "sources": manifests, "external_sources": web})
    save_lines(DATA / "normalized" / "records.jsonl", records)
    knowledge = [
        "# Kho kiến thức tuyển sinh HUST — K71 nhập học 2026",
        "",
        "Bản đọc thuận tiện của dữ liệu chuẩn. JSONL là hợp đồng nhập dữ liệu cho AI/backend.",
        "Nguồn do chủ dự án xác nhận áp dụng K71. Các mục OCR/bảng cần đối chiếu được ghi trạng thái riêng; không coi đây là xác nhận accuracy.",
        "",
    ]
    for record in records:
        if record["record_type"] == "table":
            continue
        knowledge.extend(
            [
                f"## {record['title']}",
                "",
                f"ID: `{record['record_id']}` · Chủ đề: {', '.join(record['topics'])}",
                f"Phạm vi: `{record['scope']}` · Trạng thái: `{record['review_status']}` · Lịch sử: {record['historical']}",
                f"Nguồn: `{record['source_id']}`, trang PDF {record['page_start']}–{record['page_end']}.",
                "",
                record["text"],
                "",
            ]
        )
    (DATA / "normalized" / "knowledge.md").write_text("\n".join(knowledge), encoding="utf-8")
    for topic in [*TOPICS, "institutional_rules"]:
        subset = [r for r in records if topic in r["topics"]]
        if topic == "programs":
            subset = [r for r in records if r["record_type"] == "program"]
        save_lines(DATA / "normalized" / f"{topic}.jsonl", subset)
    save_lines(DATA / "processed" / "chunks.jsonl", chunks)
    save_lines(
        DATA / "quality" / "page_inventory.jsonl",
        [
            {
                key: p[key]
                for key in [
                    "page_id",
                    "source_id",
                    "page",
                    "method",
                    "ocr_confidence",
                    "text_characters",
                    "image_count",
                    "table_ids",
                ]
            }
            for p in pages
        ],
    )
    save_lines(DATA / "quality" / "issues.jsonl", ISSUES)
    counts = Counter(topic for r in records for topic in r["topics"])
    release = {
        "release": VERSION,
        "parser_version": PARSER,
        "cohort": "K71",
        "admission_year": 2026,
        "sources": len(manifests),
        "pages": len(pages),
        "tables": len(tables),
        "records": len(records),
        "chunks": len(chunks),
        "programs": sum(r["record_type"] == "program" for r in records),
        "ocr_pages": sum(p["method"] == "ocr" for p in pages),
        "topics": dict(counts),
        "status": "technical_release_requires_content_review",
        "ready_for": ["backend_import", "retrieval_development", "reranker_evaluation"],
        "not_certified_for": ["staff_approved_admissions_advice", "accuracy_kpi"],
        "files": {},
    }
    for folder in ["manifests", "normalized", "schemas"]:
        for path in sorted((DATA / folder).glob("*")):
            if path.is_file():
                release["files"][path.relative_to(DATA).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    release["files"]["processed/chunks.jsonl"] = hashlib.sha256(
        (DATA / "processed/chunks.jsonl").read_bytes()
    ).hexdigest()
    save_json(DATA / "processed" / "release.json", release)
    lines = [
        "# Báo cáo chuẩn hóa K71 — nhập học 2026",
        "",
        f"Nguồn: {len(manifests)} PDF; trang: {len(pages)}; bảng: {len(tables)}; bản ghi: {len(records)}; chunks: {len(chunks)}.",
        "",
        "Hiệu lực K71 được chủ dự án xác nhận. Không gán năm 2026 cho dữ liệu điểm chuẩn lịch sử 2024/2025.",
        "",
        "## Nhóm dữ liệu",
        "",
        "| Nhóm | Bản ghi (có thể thuộc nhiều nhóm) |",
        "|---|---:|",
    ]
    lines += [f"| {key} | {value} |" for key, value in sorted(counts.items())]
    lines += [
        "",
        "## Các giới hạn cần xử lý",
        "",
        "- PDF gốc không đổi. sources.md đang được người dùng chỉnh nên không ghi đè.",
        "- OCR và bảng gộp/tiếp nối giữ trạng thái cần đối chiếu; raw grids không đưa vào chunks trả lời.",
        "- Native sections và chương trình đủ cấu trúc để phát triển; chưa thay thế duyệt nội dung của cán bộ.",
        "- normalized/*.jsonl là bản ghi có nguồn theo chủ đề, không phải toàn bộ bảng đã chuyển thành giá trị tính toán.",
        "- Các URL web trong sources.md chưa được đóng gói bản lưu. Học bổng tổng quan đã trích từ PDF trang 25–26; điểm chuẩn có trong PDF là lịch sử.",
        "- Không suy ra tổng học phí năm từ đơn giá TCHP, không tính điểm từ công thức OCR chưa duyệt.",
        "",
        "## Vấn đề phát hiện",
        "",
    ]
    lines += [f"- `{i['kind']}` / {i['source_id']} / trang {i['page']}: {i['detail']}" for i in ISSUES]
    (DATA / "quality" / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(release, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-ocr", action="store_true")
    build(parser.parse_args().skip_ocr)
