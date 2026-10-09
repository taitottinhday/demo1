"""Concise source-backed rendering for the local demo (no paid model needed)."""

import re

from src.services.knowledge import normalize, tokens


def structure_answer(response, sources, next_steps, manifest):
    """Expose a stable presentation contract without changing the raw response."""
    paragraphs = []
    seen = set()
    for paragraph in re.split(r"\n\s*\n", response or ""):
        lines = []
        for raw_line in paragraph.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            claim_key = normalize(re.sub(r"\s*\[\d+\]\s*$", "", line))
            if claim_key and claim_key not in seen:
                seen.add(claim_key)
                lines.append(line)
        if not lines:
            continue
        paragraphs.append(lines)
    if not paragraphs:
        paragraphs = [[response.strip()]] if response and response.strip() else []
    first = paragraphs[0] if paragraphs else [""]
    short_answer = first[0]
    conditions = first[1:] + [line for paragraph in paragraphs[1:] for line in paragraph]
    source_refs = []
    source_seen = set()
    for index, source in enumerate(sources or [], 1):
        key = (source.get("url"), source.get("page"), source.get("end_page"), source.get("version"))
        if key in source_seen:
            continue
        source_seen.add(key)
        source_refs.append(
            {
                "ref": len(source_refs) + 1,
                "title": source.get("title", "Tài liệu tuyển sinh"),
                "page": source.get("page"),
                "end_page": source.get("end_page"),
                "version": source.get("version"),
            }
        )
    version = (manifest or {}).get("version", "")[:12]
    source_count = (manifest or {}).get("document_count")
    return {
        "short_answer": short_answer,
        "conditions": conditions,
        "source_note": " · ".join(
            value
            for value in [
                f"Kho nguồn HUST · {source_count} nguồn" if source_count else "Kho nguồn HUST",
                f"bộ dữ liệu {version}" if version else "",
            ]
            if value
        ),
        "source_refs": source_refs,
        "next_steps": list(dict.fromkeys(next_steps or [])),
    }


def _admission_methods(text):
    """Extract the complete general-method list from the page-2 section."""
    match = re.search(
        r"C\u00e1c ph\u01b0\u01a1ng th\u1ee9c tuy\u1ec3n sinh:\s*(.*?)(?=\s+2\.1\.)",
        text,
        flags=re.S,
    )
    if not match:
        return []

    methods = []
    seen = set()
    for raw_item in re.split(r"\u2022\s*", match.group(1)):
        item = re.sub(r"\s+", " ", raw_item).strip(" ;")
        # A page-break overlap can leave the tail of the heading attached to
        # the preceding item. It is not part of the method name.
        item = re.sub(
            r"\s+(?:c\u00e1c\s+)?th\u1ee9c tuy\u1ec3n sinh:\s*$",
            "",
            item,
            flags=re.I,
        ).strip(" ;")
        key = normalize(item)
        if not item or key in seen:
            continue
        seen.add(key)
        methods.append(item)
    return methods


def format_answer(question, chunks, program=""):
    q = normalize(question)
    first = chunks[0]

    def add_graduation_answer(response):
        if not any(term in q for term in ["dau ra", "tot nghiep"]):
            return response
        for index, chunk in enumerate(chunks, 1):
            if chunk.get("kind") == "verified_fact" and chunk.get("topic") == "english_graduation":
                return response + f"\n\nChuẩn ngoại ngữ đầu ra: {chunk.get('answer_vi', '').strip()} [{index}]"
        return response + "\n\nMình chưa tìm thấy quy định đầu ra phù hợp với chương trình trong nguồn hiện có; cần cán bộ kiểm tra."

    result_date = any(t in q for t in ["ket qua", "trung tuyen", "diem chuan"]) and any(
        t in q for t in ["khi nao", "bao gio", "ngay nao", "thoi gian", "thong bao", "cong bo"]
    )
    if result_date:
        for i, chunk in enumerate(chunks, 1):
            match = re.search(r"Thông báo trúng tuyển:\s*([^.]+)\.", chunk["text"])
            if match:
                return (
                    f"Theo mục 6.2 về xét tuyển theo kết quả Đánh giá tư duy trong tài liệu HUST 2026, mốc thông báo trúng tuyển là {match.group(1)}. [{i}]\n\n"
                    "Đây là lịch ghi trong tài liệu, không phải xác nhận kết quả đã được công bố. "
                    "Nếu bạn hỏi phương thức khác hoặc tình trạng công bố hiện tại, cần kiểm tra thông báo chính thức đúng phương thức."
                )
        return None
    if first.get("kind") == "verified_fact":
        claims = []
        seen_facts = set()
        for i, chunk in enumerate(chunks, 1):
            if chunk.get("kind") != "verified_fact":
                continue
            answer = re.sub(r"\s+", " ", chunk.get("answer_vi", "")).strip()
            scope = re.sub(r"\s+", " ", chunk.get("scope_vi", "")).strip()
            if not answer:
                continue
            key = normalize(answer)
            if key in seen_facts:
                continue
            seen_facts.add(key)
            if scope and normalize(scope) not in normalize(answer):
                answer += f" Lưu ý: {scope}"
            claims.append(f"{answer} [{i}]")
        return "\n\n".join(claims[:3]) or None
    if not program and "phuong thuc" in q:
        for i, chunk in enumerate(chunks, 1):
            methods = _admission_methods(chunk["text"])
            if len(methods) >= 3:
                return "Các phương thức tuyển sinh chung toàn trường trong tài liệu HUST 2026:\n\n" + "\n".join(
                    f"• {item} [{i}]" for item in methods
                )
    if first["kind"] in {"fee", "overview"}:
        return first["text"] + " [1]"
    if first["kind"] == "program" and any(t in q for t in ["phuong thuc", "to hop", "xet tuyen"]):
        text = first["text"]
        methods = []
        if "Phương thức XTTN" in text:
            methods.append("• Xét tuyển tài năng (XTTN). [1]")
        if "Phương thức ĐGTD" in text:
            methods.append("• Xét tuyển theo kết quả thi Đánh giá tư duy (ĐGTD). [1]")
        thpt = re.search(r"Phương thức THPT\s*\((.+)\)\.", text)
        if thpt:
            methods.append(f"• Xét tuyển theo kết quả thi tốt nghiệp THPT; tổ hợp: {thpt.group(1)}. [1]")
        if methods:
            return f"{first['code']} — {first['title']} có các phương thức xét tuyển:\n\n" + "\n".join(methods)
    if "dang ky" in q and any(t in q for t in ["tu duy", "tsa", "dgtd"]):
        for i, chunk in enumerate(chunks, 1):
            text = chunk["text"]
            if "https://tsa.hust.edu.vn/dk" in text and "https://thisinh.thitotnghiepthpt.edu.vn/Account/Login" in text:
                return (
                    "Có hai bước đăng ký khác nhau:\n\n"
                    f"1. Đăng ký dự thi Đánh giá tư duy tại https://tsa.hust.edu.vn/dk. [{i}]\n"
                    "2. Đăng ký nguyện vọng xét tuyển bằng tài khoản thí sinh trên hệ thống của Bộ: "
                    f"https://thisinh.thitotnghiepthpt.edu.vn/Account/Login, theo kế hoạch chung. [{i}]\n\n"
                    f"Đăng ký dự thi không thay thế đăng ký nguyện vọng xét tuyển. [{i}]"
                )
    if "dia chi" in q:
        for i, chunk in enumerate(chunks, 1):
            match = re.search(r"Số 1 Đại Cồ Việt[^.]+\.", chunk["text"])
            if match:
                return f"Địa chỉ HUST: {match.group(0)} [{i}]"
    if "k01" in q and "he so" in q:
        for i, chunk in enumerate(chunks, 1):
            match = re.search(r"Tổ hợp K01 \(Toán, Văn,[^.]+\.", chunk["text"])
            if match:
                return match.group(0) + f" [{i}]"
    if (
        any(t in q for t in ["ngoai ngu", "ielts", "vstep"])
        and "quy doi" not in q
        and not any(t in q for t in ["phi", "xac thuc", "diem thuong"])
    ):
        for i, chunk in enumerate(chunks, 1):
            text = chunk["text"]
            if all(t in text for t in ["5.0", "6.5", "5.5", "VSTEP"]):
                row = next(((n, c) for n, c in enumerate(chunks, 1) if c.get("code") == program and program), None)
                if row:
                    n, c = row
                    name = c["title"]
                    english_advanced = "tien tien" in normalize(name) and "Chương trình học bằng tiếng Anh" in c["text"]
                    if english_advanced or program in {"FL1", "FL3", "FL4"}:
                        subject = {"FL3": "tiếng Trung", "FL4": "tiếng Hàn"}.get(program, "tiếng Anh")
                        return add_graduation_answer(
                            f"{program} — {name}: ngoài các điều kiện xét tuyển khác, bạn cần đáp ứng một trong các điều kiện ngoại ngữ đầu vào sau. [{n}] [{i}]\n\n"
                            f"• VSTEP B1 trở lên. [{i}]\n"
                            f"• IELTS Academic 5.0 trở lên hoặc tương đương. [{i}]\n"
                            f"• Điểm thi tốt nghiệp THPT 2026 môn {subject} từ 6.5 trở lên. [{i}]"
                        )
                    if program in {"TROYIT", "FL2"}:
                        return add_graduation_answer(
                            f"{program} — {name}: ngoài các điều kiện xét tuyển khác, yêu cầu IELTS Academic từ 5.5 trở lên. [{n}] [{i}]"
                        )
                if program == "IT1":
                    program_source = next((n for n, c in enumerate(chunks, 1) if c.get("code") == "IT1"), None)
                    if program_source is None:
                        return None
                    return add_graduation_answer(
                        f"IT1 là chương trình CNTT: Khoa học Máy tính. [{program_source}]\n\n"
                        "Mục 5.2 của tài liệu tuyển sinh 2026 không nêu IT1 trong nhóm chương trình phải đáp ứng "
                        f"ngưỡng ngoại ngữ đầu vào riêng như IELTS 5.0/5.5. Vì vậy, không áp các ngưỡng đó cho IT1. [{i}]\n\n"
                        "Nếu bạn dùng chứng chỉ ngoại ngữ để quy đổi điểm hoặc cộng điểm thưởng, "
                        f"chứng chỉ cần đăng ký xác thực trên https://ts-hn.hust.edu.vn/ theo quy định. [{i}]\n\n"
                        "Điều này không áp dụng thay cho chuẩn ngoại ngữ đầu ra."
                    )
                response = (
                    "Về ngoại ngữ đầu vào, tài liệu HUST 2026 quy định:\n\n"
                    "• Chương trình tiên tiến giảng dạy bằng tiếng Anh và FL1, FL3, FL4: đáp ứng một trong các điều kiện "
                    "VSTEP B1 trở lên; IELTS Academic 5.0 trở lên hoặc tương đương; hoặc điểm thi THPT 2026 môn ngoại ngữ "
                    f"từ 6.5 (tiếng Anh, tiếng Trung đối với FL3, tiếng Hàn đối với FL4). [{i}]\n"
                    f"• Chương trình liên kết TROY-IT và FL2: IELTS Academic 5.5 trở lên. [{i}]\n\n"
                    f"Các yêu cầu này đi kèm những điều kiện xét tuyển khác, không áp dụng chung cho mọi chương trình. [{i}]"
                )
                return add_graduation_answer(response)
    # Pick complete relevant sentences; never dump an entire retrieved PDF chunk.
    query = set(tokens(question))
    paragraphs = []
    seen = set()
    for i, chunk in enumerate(chunks, 1):
        text = re.sub(r"^\d+\s+", "", chunk["text"])
        sentences = re.split(r"(?<=[.;])\s+(?=[A-ZÀ-Ỹ(•+-])", text)
        ranked = sorted(
            enumerate(sentences),
            key=lambda pair: len(query & set(tokens(pair[1]))),
            reverse=True,
        )
        chosen = sorted(index for index, sentence in ranked[:2] if query & set(tokens(sentence)))
        for index in chosen:
            sentence = sentences[index].strip()
            if len(sentence) <= 850:
                sentence = re.sub(r"\s+\d+\.$", "", sentence)
                key = normalize(sentence)
                if key and key not in seen:
                    seen.add(key)
                    paragraphs.append(f"{sentence} [{i}]")
        if len(paragraphs) >= 3:
            break
    return "\n\n".join(paragraphs[:3]) or None
