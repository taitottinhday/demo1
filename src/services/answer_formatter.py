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
    if chunks and chunks[0].get("cutoff_methods"):
        c = chunks[0]
        q = normalize(question)
        requested = [method for method in c["cutoff_methods"] if (
            (method == "THPT" and "thpt" in q)
            or (method == "TSA" and any(w in q for w in ["tsa", "dgtd", "danh gia tu duy"]))
            or (method.startswith("XTTN") and any(w in q for w in ["xttn", "xet tuyen tai nang", "1.2", "1.3"])
                and (not re.search(r"1\.[23]", q) or method[-3:] in q))
        )]
        methods = requested or list(c["cutoff_methods"])
        if any(word in q for word in ["co nghia", "tuong duong"]):
            methods = list(c["cutoff_methods"])
        scores = "; ".join(f"{method}: {c['cutoff_methods'][method].replace('.', ',')}/{30 if method == 'THPT' else 100}"
                           for method in methods)
        return (f"Điểm chuẩn {c.get('program_name', c['program_code'])} ({c['program_code']}) năm 2026: {scores}. [1]\n\n"
                f"Tổ hợp gốc {c['base_combination']}. XTTN 1.2, XTTN 1.3 và TSA là điểm chuẩn tương đương "
                "được công bố trong bảng chính thức, không phải phép tự quy đổi điểm cá nhân. [1]")
    if chunks and all(c.get("historical") and c.get("record_type") == "cutoff" for c in chunks):
        code = chunks[0].get("program_codes", [program])[0]
        year = chunks[0]["admission_year"]
        name = chunks[0].get("program_name") or code
        lines = [f"Điểm chuẩn {name} năm {year}:"]
        for i, c in enumerate(chunks, 1):
            method = "ĐGTD (TSA)" if c.get("method") in {"DGTD", "ĐGTD"} else c["method"]
            score = re.search(r":\s*(\d+(?:[.,]\d+)?/\d+(?:[.,]\d+)?)", c["text"])
            if not score:
                return None
            lines.append(f"• {method}: {score[1].replace('.', ',')} điểm. [{i}]")
        notes = "Đây là điểm lịch sử, không áp dụng thay cho điểm chuẩn năm 2026."
        if any(c.get("method") == "XTTN" for c in chunks):
            notes = "Bảng nguồn ghi chung XTTN, không tách diện 1.2 và 1.3. " + notes
        return lines[0] + " " + "; ".join(line.removeprefix("• ") for line in lines[1:]) + "\n\n" + notes
    if "hoc bong" in normalize(question):
        names = [name for name in (
            "tran dai nghia", "khuyen khich hoc tap", "gan ket que huong", "trao doi sinh vien"
        ) if name in normalize(question)]
        sections = []
        for index, chunk in enumerate(chunks, 1):
            if normalize(chunk["title"]) != "12.4 hoc bong" or not chunk.get("record_id"):
                continue
            if not names and all(term in normalize(chunk["text"]) for term in [
                "1,5", "tran dai nghia", "50%", "100%", "loai xuat sac"
            ]):
                return (
                    f"Điều kiện phụ thuộc từng loại học bổng; tài liệu nêu hai nhóm chính sách sau. [{index}]\n\n"
                    f"• Khuyến khích học tập: xét theo học kỳ dựa trên kết quả học tập và rèn luyện. "
                    f"Mức khá, giỏi, xuất sắc yêu cầu cả hai kết quả đạt từ loại tương ứng trở lên. "
                    f"Học bổng loại khá tương đương học phí phải đóng; loại giỏi bằng 1,2 lần, loại xuất sắc bằng 1,5 lần mức khá. [{index}]\n\n"
                    f"• Trần Đại Nghĩa: dành cho sinh viên có hoàn cảnh kinh tế gia đình đặc biệt khó khăn, "
                    f"có ý chí và nghị lực vươn lên; xét theo học kỳ, với mức 50% hoặc 100% học phí. [{index}]\n\n"
                    f"Tài liệu còn nêu học bổng tài trợ, gắn kết quê hương và trao đổi sinh viên quốc tế. [{index}]\n\n"
                    "Bạn muốn tìm hiểu loại nào? Điều kiện chính sách không đồng nghĩa chắc chắn được cấp; "
                    "hồ sơ và thời hạn cần theo thông báo từng đợt."
                )
            for section in re.split(r"(?=\([1-5]\) Học bổng)", chunk["text"]):
                if not re.match(r"\([1-5]\) Học bổng", section):
                    continue
                if names and not any(name in normalize(section) for name in names):
                    continue
                # Quote complete source sections, including conditions and limits.
                section = re.split(r"Chi tiết tại địa chỉ:", section)[0].strip()
                sections.append(f"{section} [{index}]")
        if sections:
            return "Thông tin học bổng trong tài liệu tuyển sinh 2026:\n\n" + "\n\n".join(sections) + (
                "\n\nĐây là thông tin chính sách, không xác nhận bạn được cấp học bổng. "
                "Hồ sơ, thời hạn và kết quả xét cấp cần đối chiếu thông báo của từng học bổng."
            )
    q = normalize(question)
    first = chunks[0]
    if "chon" in q and any(term in q for term in ["thoi diem", "khi nao"]) and "tich hop" in q:
        for i, c in enumerate(chunks, 1):
            match = re.search(r"Sinh viên có thể xem xét.*?cuối năm thứ 3.*?\.", c["text"])
            if match:
                return f"{match[0]} [{i}]"
    if "lien ket dao tao quoc te" in q and any(term in q for term in ["nao", "liet ke"]):
        for i, c in enumerate(chunks, 1):
            match = re.search(r"Các chương trình liên kết đào tạo quốc tế gồm.*?\.", c["text"])
            if match:
                return f"{match[0]} [{i}]"
    if program and any(word in q for word in ["ngoai ngu", "ielts", "tieng anh"]) and not any(
        word in q for word in ["dau ra", "tot nghiep", "quy doi", "xac thuc"]
    ):
        rule = next((i for i, c in enumerate(chunks, 1)
                     if c.get("page") == 16 and "VSTEP" in c["text"] and "5.5" in c["text"]), None)
        row = next(((i, c) for i, c in enumerate(chunks, 1)
                    if c.get("kind") == "program" and c.get("code") == program), None)
        if rule and row:
            index, item = row
            label = f"{item['title']} ({program})"
            language_rule = item.get("program_profile", {}).get("entrance_language_rule")
            if language_rule == "ielts_5_5":
                return (f"{label} yêu cầu IELTS Academic từ 5.5 trở lên về ngoại ngữ đầu vào. [{rule}][{index}]\n\n"
                        "Điều kiện này đi kèm các điều kiện xét tuyển khác; chuẩn đầu ra khi tốt nghiệp được quy định riêng.")
            if language_rule == "entrance_options":
                subject = "tiếng Trung" if program == "FL3" else "tiếng Hàn" if program == "FL4" else "tiếng Anh"
                return (f"{label} cần đáp ứng ít nhất một điều kiện ngoại ngữ đầu vào sau. [{rule}][{index}]\n\n"
                        f"• VSTEP từ B1 trở lên; hoặc IELTS Academic từ 5.0 trở lên (hoặc tương đương); "
                        f"hoặc điểm thi tốt nghiệp THPT năm 2026 môn {subject} từ 6.5 trở lên. [{rule}]\n\n"
                        "Không bắt buộc riêng chứng chỉ IELTS nếu đáp ứng một lựa chọn khác theo quy định. "
                        "Các điều kiện xét tuyển khác và chuẩn ngoại ngữ đầu ra được áp dụng riêng.")
            if language_rule == "no_specific_entrance_requirement":
                return (f"{label} là chương trình chuẩn, không thuộc nhóm có điều kiện ngoại ngữ đầu vào riêng "
                        f"tại mục 5.2. [{rule}][{index}]\n\n"
                        f"Mục này không nêu ngưỡng chứng chỉ riêng cho {program}; không áp ngưỡng IELTS/VSTEP "
                        f"của chương trình tiên tiến cho chương trình chuẩn. [{rule}]\n\n"
                        "Việc dùng chứng chỉ để quy đổi/cộng điểm xét tuyển và chuẩn ngoại ngữ đầu ra là các quy định riêng.")
            return (f"{label} có đặc thù chương trình cần đối chiếu riêng. [{index}] "
                    f"Mục 5.2 chỉ nêu các nhóm có ngưỡng ngoại ngữ cụ thể; chưa đủ căn cứ để gán một ngưỡng "
                    f"IELTS/VSTEP riêng cho {program}. [{rule}] Bạn có thể nhờ cán bộ kiểm tra yêu cầu của chương trình.")

    if first.get("kind") == "program" and any(term in q for term in ["chi tieu", "quota"]):
        requested_code = program or first.get("code", "")
        row_index = next(
            (
                index
                for index, chunk in enumerate(chunks, 1)
                if chunk.get("kind") == "program" and chunk.get("code") == requested_code
            ),
            None,
        )
        if row_index is not None:
            row = chunks[row_index - 1]
            quota = re.search(r"Chỉ tiêu năm 2026:\s*([^.;]+)", row.get("text", ""), flags=re.I)
            if quota:
                return (
                    f"{row['code']} — {row['title']}: chỉ tiêu tuyển sinh năm 2026 là "
                    f"{quota.group(1).strip()}. [{row_index}]"
                )

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
                if any(term in q for term in ["yeu cau", "dieu kien", "can gi"]) and not any(
                    term in q for term in ["quy trinh", "nhu the nao"]
                ):
                    condition = re.search(r"Thí sinh đã tốt nghiệp THPT.*?(?:;|\.)", text)
                    if condition:
                        return f"{condition[0].rstrip(';')}. [{i}]"
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
