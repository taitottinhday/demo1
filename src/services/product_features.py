"""Source-backed comparison."""

from src.services.answer_formatter import format_answer


def compare_programs(knowledge, codes):
    result = []
    rules = next((c for c in knowledge.chunks if c["page"] == 16 and "VSTEP" in c["text"] and "5.5" in c["text"]), None)
    for code in codes:
        program = next(p for p in knowledge.programs if p["code"] == code)
        chunk = next(c for c in knowledge.chunks if c["kind"] == "program" and c["code"] == code)
        fee = knowledge.search(f"Học phí {code}", code, limit=1)
        language = "Chưa đủ nguồn xác nhận điều kiện riêng; cần cán bộ kiểm tra."
        if rules:
            response = format_answer(f"Điều kiện ngoại ngữ {code}", [rules, chunk], code)
            if code in {"IT1", "FL1", "FL2", "FL3", "FL4", "TROYIT"} or (
                "tiên tiến" in program["name"].lower() and "Chương trình học bằng tiếng Anh" in chunk["text"]
            ):
                language = response or language
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
            }
        )
    return result

