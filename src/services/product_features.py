"""Source-backed comparison."""

import re

from src.services.answer_formatter import format_answer
from src.services.knowledge import normalize

FIELD_AVAILABLE = "available"
FIELD_NO_SPECIFIC_REQUIREMENT = "no_specific_requirement"
FIELD_MISSING = "missing"


def _compact_source_text(text):
    return re.sub(r"[^a-z0-9]+", "", normalize(text or ""))


def _has_program_specific_language_rule(program, chunk, rules):
    """Determine scope from the wording in the source, not a code allow-list."""
    if not rules:
        return False
    code = _compact_source_text(program["code"])
    rule_text = _compact_source_text(rules["text"])
    if code and code in rule_text:
        return True
    program_text = normalize(f"{program['name']} {chunk['text']}")
    return "tien tien" in program_text and "chuong trinh hoc bang tieng anh" in program_text


def _no_specific_language_message(program):
    return (
        f"{program['code']} — {program['name']}: nguồn tuyển sinh 2026 không nêu mã này trong "
        "các nhóm chương trình có ngưỡng ngoại ngữ đầu vào riêng. Vì vậy, chưa thấy yêu cầu "
        "riêng cho chương trình này trong nguồn. Đây không phải xác nhận chuẩn ngoại ngữ đầu ra."
    )


def _field_status(status, reason):
    return {"status": status, "reason": reason}


def compare_programs(knowledge, codes):
    result = []
    rules = next((c for c in knowledge.chunks if c["page"] == 16 and "VSTEP" in c["text"] and "5.5" in c["text"]), None)
    for code in codes:
        program = next(p for p in knowledge.programs if p["code"] == code)
        chunk = next(c for c in knowledge.chunks if c["kind"] == "program" and c["code"] == code)
        fee = knowledge.search(f"Học phí {code}", code, limit=1)
        language = "Chưa đủ nguồn xác nhận điều kiện riêng; cần cán bộ kiểm tra."
        language_status = FIELD_MISSING
        language_reason = "Chưa có nội dung và nguồn đủ để kết luận về trường này."
        if rules and not _has_program_specific_language_rule(program, chunk, rules):
            language = _no_specific_language_message(program)
            language_status = FIELD_NO_SPECIFIC_REQUIREMENT
            language_reason = "Nguồn không nêu yêu cầu ngoại ngữ đầu vào riêng cho mã này."
        elif rules:
            response = format_answer(f"Điều kiện ngoại ngữ {code}", [rules, chunk], code)
            if response:
                language = response
                language_status = FIELD_AVAILABLE
                language_reason = "Có nội dung và nguồn trực tiếp trong tài liệu."
        field_status = {
            "quota": _field_status(
                FIELD_AVAILABLE if str(program["quota"] or "").strip() else FIELD_MISSING,
                "Có chỉ tiêu trong dòng chương trình." if program["quota"] else "Chưa có chỉ tiêu trong nguồn.",
            ),
            "methods": _field_status(
                FIELD_AVAILABLE if str(program["methods"] or "").strip() else FIELD_MISSING,
                "Có phương thức trong dòng chương trình." if program["methods"] else "Chưa có phương thức trong nguồn.",
            ),
            "fee": _field_status(
                FIELD_AVAILABLE if fee else FIELD_MISSING,
                "Có mức học phí và nguồn tương ứng." if fee else "Chưa ghép được mức học phí từ nguồn.",
            ),
            "language": _field_status(language_status, language_reason),
            "note": _field_status(
                FIELD_AVAILABLE if str(program["note"] or "").strip() else FIELD_NO_SPECIFIC_REQUIREMENT,
                "Có ghi chú trong dòng chương trình."
                if program["note"]
                else "Nguồn không nêu ghi chú riêng trong dòng chương trình.",
            ),
        }
        result.append(
            {
                "code": code,
                "name": program["name"],
                "quota": program["quota"],
                "methods": program["methods"],
                "note": program["note"] or "Không có ghi chú riêng trong bảng.",
                "fee": fee[0]["text"] if fee else "Chưa ghép được mức học phí từ nguồn; cần cán bộ kiểm tra.",
                "language": language,
                "sources": {
                    "program": knowledge.citation(chunk),
                    "fee": knowledge.citation(fee[0]) if fee else None,
                    "language": knowledge.citation(rules) if rules else None,
                },
                "field_status": field_status,
            }
        )
    return result

