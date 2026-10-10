"""Private, source-linked exploration suggestions from the loaded HUST catalog.

The current admissions source contains program names and admissions details, but
not curriculum or career outcome data. Matching is therefore intentionally
limited to transparent topic/name overlap and never scores a student's ability.
"""

import re

from src.services.knowledge import normalize

AREAS = (
    {
        "id": "computing",
        "label": "Máy tính và công nghệ thông tin",
        "program_terms": (
            "cntt",
            "khoa hoc may tinh",
            "ky thuat may tinh",
            "cong nghe thong tin",
            "may tinh",
            "an toan khong gian so",
            "he thong thong tin",
            "iot",
            "he thong nhung",
        ),
        "input_terms": (
            "cntt",
            "khoa hoc may tinh",
            "cong nghe thong tin",
            "may tinh",
            "an toan khong gian so",
            "he thong thong tin",
            "iot",
            "he thong nhung",
            "lap trinh",
            "phan mem",
            "code",
            "coding",
            "python",
            "giai thuat",
            "algorithm",
            "cyber security",
            "an ninh mang",
        ),
    },
    {
        "id": "data_ai",
        "label": "Dữ liệu và trí tuệ nhân tạo",
        "program_terms": ("du lieu", "tri tue nhan tao", "khoa hoc tinh toan", "he thong thong minh"),
        "input_terms": (
            "du lieu",
            "tri tue nhan tao",
            "khoa hoc tinh toan",
            "he thong thong minh",
            "phan tich du lieu",
            "machine learning",
            "hoc may",
            "ai",
            "data science",
            "toan",
            "thong ke",
            "tu duy logic",
            "mathematics",
            "math",
        ),
    },
    {
        "id": "electrical",
        "label": "Điện, điện tử và tự động hóa",
        "program_terms": ("dien tu", "ky thuat dien", "tu dong hoa", "nang luong", "vien thong", "he thong dien"),
        "input_terms": (
            "dien tu",
            "ky thuat dien",
            "tu dong hoa",
            "nang luong",
            "vien thong",
            "he thong dien",
            "mach dien",
            "robot",
            "vat ly",
            "mon ly",
        ),
    },
    {
        "id": "mechanical",
        "label": "Cơ khí và cơ điện tử",
        "program_terms": ("co khi", "co dien tu", "che tao", "nhiet", "dong luc"),
        "input_terms": ("co khi", "co dien tu", "che tao", "nhiet", "dong luc", "may moc", "robot"),
    },
    {
        "id": "vehicles_aerospace",
        "label": "Ô tô và hàng không",
        "program_terms": ("o to", "hang khong", "co khi hang khong"),
        "input_terms": ("o to", "hang khong", "co khi hang khong", "may bay", "phuong tien"),
    },
    {
        "id": "chemistry_materials",
        "label": "Hóa học và vật liệu",
        "program_terms": (
            "hoa hoc",
            "hoa duoc",
            "hoa my pham",
            "vat lieu",
            "polyme",
            "compozit",
            "vi dien tu",
            "nano",
            "ky thuat in",
        ),
        "input_terms": (
            "hoa hoc",
            "hoa duoc",
            "hoa my pham",
            "vat lieu",
            "polyme",
            "compozit",
            "vi dien tu",
            "nano",
            "ky thuat in",
            "hoa",
            "mon hoa",
        ),
    },
    {
        "id": "biology_food_environment",
        "label": "Sinh học, thực phẩm và môi trường",
        "program_terms": ("sinh hoc", "thuc pham", "moi truong", "tai nguyen"),
        "input_terms": (
            "sinh hoc",
            "thuc pham",
            "moi truong",
            "tai nguyen",
            "cong nghe sinh hoc",
            "cong nghe thuc pham",
            "mon sinh",
            "mon sinh hoc",
        ),
    },
    {
        "id": "business_management",
        "label": "Kinh doanh và quản lý",
        "program_terms": ("kinh doanh", "quan ly", "tai chinh", "ke toan", "logistics", "chuoi cung ung"),
        "input_terms": ("kinh doanh", "quan ly", "tai chinh", "ke toan", "logistics", "chuoi cung ung", "marketing"),
    },
    {
        "id": "education_psychology",
        "label": "Giáo dục và tâm lý",
        "program_terms": ("giao duc", "tam ly"),
        "input_terms": ("giao duc", "tam ly", "hoc tap", "dao tao"),
    },
    {
        "id": "languages_media",
        "label": "Ngôn ngữ và truyền thông",
        "program_terms": ("tieng anh", "tieng trung", "tieng han", "truyen thong so", "da phuong tien"),
        "input_terms": (
            "tieng anh",
            "tieng trung",
            "tieng han",
            "ngoai ngu",
            "ngon ngu",
            "truyen thong so",
            "da phuong tien",
            "thiet ke",
            "noi dung so",
            "english",
            "anh van",
            "mon anh",
        ),
    },
    {
        "id": "physics_sciences",
        "label": "Vật lý và khoa học ứng dụng",
        "program_terms": ("vat ly", "hat nhan", "khoa hoc tinh toan"),
        "input_terms": ("vat ly", "hat nhan", "khoa hoc tinh toan", "quang hoc", "khoa hoc tu nhien", "mon ly"),
    },
)

AREA_BY_ID = {area["id"]: area for area in AREAS}
NOTICE = (
    "Đây là đối chiếu từ khóa bạn cung cấp với tên chương trình trong tài liệu tuyển sinh HUST 2026, không phải đánh giá mức độ phù hợp. "
    "Nguồn hiện có chưa đủ để xác nhận nội dung học, trọng tâm phần mềm, nghề nghiệp hay cơ hội trúng tuyển. "
    "Mục tiêu phát triển không làm giảm gợi ý. Nội dung được gửi tới máy chủ website để đối chiếu, không gửi tới AI bên ngoài "
    "và không lưu vào hội thoại hoặc ticket."
)


def _plain(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", normalize(value or "")).strip()


def _contains(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def _text_areas(value: str) -> set[str]:
    text = _plain(value)
    if not text:
        return set()
    return {area["id"] for area in AREAS if any(_contains(text, _plain(term)) for term in area["input_terms"])}


def _split_criteria(value: str) -> list[str]:
    """Keep short user-entered criteria so explanations can point to their origin."""
    parts = re.split(r"[,;，；\n]+|\s+(?:và|and)\s+", value or "", flags=re.IGNORECASE)
    return [part.strip(" \t.-")[:120] for part in parts if part.strip(" \t.-")]


def _text_criteria(value: str) -> tuple[list[dict], list[str]]:
    matches, unmatched = [], []
    for phrase in _split_criteria(value):
        areas = sorted(_text_areas(phrase))
        if not areas:
            unmatched.append(phrase)
            continue
        matches.extend({"area_id": area_id, "criterion": phrase} for area_id in areas)
    return matches, unmatched


def _program_name_terms(name: str, area: dict) -> list[str]:
    """Return the exact, accent-preserving phrases from the loaded program name."""
    normalized_words = re.findall(r"[a-z0-9]+", _plain(name))
    original_words = list(re.finditer(r"[^\W_]+", name, flags=re.UNICODE))
    found = []
    for term in area["program_terms"]:
        target = re.findall(r"[a-z0-9]+", _plain(term))
        if not target or len(target) > len(normalized_words):
            continue
        for start in range(len(normalized_words) - len(target) + 1):
            if normalized_words[start : start + len(target)] != target:
                continue
            first, last = original_words[start], original_words[start + len(target) - 1]
            found.append(name[first.start() : last.end()])
            break
    # Suppress short terms already covered by a more specific phrase.
    normalized_found = [(term, _plain(term)) for term in dict.fromkeys(found)]
    return [
        term
        for term, plain in normalized_found
        if not any(plain != other and _contains(other, plain) for _, other in normalized_found)
    ]


def _profile_group(selected: list[str], note: str) -> list[str]:
    values = [AREA_BY_ID[key]["label"] for key in selected if key in AREA_BY_ID]
    if note.strip():
        values.append(note.strip()[:160] + ("…" if len(note.strip()) > 160 else ""))
    return list(dict.fromkeys(values))


def _profile_summary(profile) -> dict:
    return {
        "strengths": _profile_group(profile.strengths, profile.strengths_note),
        "interests": _profile_group(profile.interests, profile.interests_note),
        "direction": [profile.career_direction.strip()[:160] + ("…" if len(profile.career_direction.strip()) > 160 else "")] if profile.career_direction.strip() else [],
        "development_goals": _profile_group(profile.improvements, profile.improvements_note),
        "priorities": [profile.priorities.strip()[:160] + ("…" if len(profile.priorities.strip()) > 160 else "")] if profile.priorities.strip() else [],
    }


def _profile_criteria(profile) -> tuple[dict[str, list[dict]], list[dict]]:
    groups = {
        "Thế mạnh": (profile.strengths, profile.strengths_note),
        "Sở thích": (profile.interests, profile.interests_note),
        "Định hướng": ([], profile.career_direction),
        "Tiêu chí ưu tiên": ([], profile.priorities),
    }
    result, unmatched = {}, []
    for label, (selected, note) in groups.items():
        criteria = [{"area_id": key, "criterion": AREA_BY_ID[key]["label"]} for key in selected if key in AREA_BY_ID]
        text_matches, text_unmatched = _text_criteria(note)
        criteria.extend(text_matches)
        result[label] = criteria
        if text_unmatched:
            unmatched.append({
                "group": label,
                "criteria": text_unmatched,
                "message": "Chưa đủ dữ liệu để đối chiếu tiêu chí này với tên chương trình trong nguồn tuyển sinh.",
            })
    development_goals = _profile_group(profile.improvements, profile.improvements_note)
    if development_goals:
        unmatched.append({
            "group": "Mục tiêu phát triển",
            "criteria": development_goals,
            "message": "Chưa đủ dữ liệu để đối chiếu mục tiêu với nội dung từng chương trình. Mục tiêu này không được dùng để xếp hạng hay làm giảm gợi ý.",
        })
    return result, unmatched


def _criteria_matches_by_program(program_areas: dict[str, list[str]], profile_criteria: dict) -> list[dict]:
    matches = []
    for label, criteria in profile_criteria.items():
        grouped = {}
        for criterion in criteria:
            area_id = criterion["area_id"]
            if area_id not in program_areas:
                continue
            entry = grouped.setdefault(area_id, {"group": label, "criteria": [], "topic": AREA_BY_ID[area_id]["label"]})
            if criterion["criterion"] not in entry["criteria"]:
                entry["criteria"].append(criterion["criterion"])
        for area_id, entry in grouped.items():
            entry["program_name_terms"] = program_areas[area_id]
            matches.append(entry)
    return matches


def _criteria_not_matched_by_program(program_areas: set[str], profile_criteria: dict) -> list[dict]:
    grouped = {}
    for label, criteria in profile_criteria.items():
        for criterion in criteria:
            area_id = criterion["area_id"]
            if area_id in program_areas:
                continue
            entry = grouped.setdefault(
                (label, area_id),
                {
                    "group": label,
                    "topic": AREA_BY_ID[area_id]["label"],
                    "criteria": [],
                    "message": "Chưa đủ dữ liệu để đối chiếu tiêu chí này với tên chương trình.",
                },
            )
            if criterion["criterion"] not in entry["criteria"]:
                entry["criteria"].append(criterion["criterion"])
    return list(grouped.values())


def recommendation_options(knowledge):
    """Return only topic groups represented in the actual loaded program catalog."""
    names = [_plain(program.get("name", "")) for program in knowledge.programs]
    areas = [
        {"id": area["id"], "label": area["label"]}
        for area in AREAS
        if any(any(_contains(name, _plain(term)) for term in area["program_terms"]) for name in names)
    ]
    return {"areas": areas, "notice": NOTICE}


def recommend_programs(knowledge, profile):
    """Rank at most three catalog programs by user-selected topic overlap.

    Development goals are summarized for the candidate but never affect a rank.
    Free-text is processed in memory and is not saved to chat or ticket records.
    """
    allowed_areas = {area["id"] for area in AREAS}
    profile_criteria, unmatched_criteria = _profile_criteria(profile)
    strengths = {item["area_id"] for item in profile_criteria["Thế mạnh"]} & allowed_areas
    interests = (
        {item["area_id"] for label in ("Sở thích", "Định hướng", "Tiêu chí ưu tiên") for item in profile_criteria[label]}
        & allowed_areas
    )
    profile_summary = _profile_summary(profile)

    selected = strengths | interests
    if not selected:
        return {
            "suggestions": [],
            "profile_summary": profile_summary,
            "unmatched_criteria": unmatched_criteria,
            "notice": NOTICE,
            "message": "Chưa có chủ đề nào trong mô tả khớp với tên chương trình hiện có. Hãy chọn lĩnh vực ở các gợi ý hoặc thử mô tả bằng tên môn học/lĩnh vực cụ thể hơn.",
        }

    programs_by_code = {item["code"]: item for item in knowledge.programs}
    chunks_by_code = {
        chunk["code"]: chunk
        for chunk in knowledge.chunks
        if chunk.get("kind") == "program" and chunk.get("code") in programs_by_code
    }
    ranked = []
    for code, program in programs_by_code.items():
        name = _plain(program.get("name", ""))
        program_area_terms = {
            area["id"]: _program_name_terms(program["name"], area)
            for area in AREAS
            if any(_contains(name, _plain(term)) for term in area["program_terms"])
        }
        program_areas = set(program_area_terms)
        matched_strengths = sorted(strengths & program_areas)
        matched_interests = sorted(interests & program_areas)
        score = 2 * len(matched_strengths) + 3 * len(matched_interests)
        chunk = chunks_by_code.get(code)
        if score <= 0 or chunk is None:
            continue

        criteria_matches = _criteria_matches_by_program(program_area_terms, profile_criteria)
        criteria_not_matched = _criteria_not_matched_by_program(program_areas, profile_criteria)
        reasons = ["Tên chương trình có từ khóa thuộc lĩnh vực bạn đã nêu."]
        considerations = ["Chưa đủ dữ liệu để xác nhận nội dung học hoặc mức độ thiên về phần mềm; căn cứ hiện tại chỉ là tên chương trình."]

        citation = knowledge.citation(chunk)
        ranked.append(
            {
                "score": score,
                "code": code,
                "name": program["name"],
                "badge": "Đối chiếu theo tên",
                "reasons": reasons,
                "matched_strengths": [AREA_BY_ID[key]["label"] for key in matched_strengths],
                "matched_interests": [AREA_BY_ID[key]["label"] for key in matched_interests],
                "criteria_matches": criteria_matches,
                "unmatched_criteria": criteria_not_matched,
                "insufficient_data": considerations,
                "considerations": considerations,
                "_program_areas": program_areas,
                "source": {
                    "title": citation["title"],
                    "page": citation["page"],
                    "end_page": citation["end_page"],
                    "local_url": citation["local_url"],
                    "url": citation["url"],
                    "version": citation["version"],
                    "document_status": citation["document_status"],
                },
            }
        )

    ranked.sort(key=lambda item: (-item["score"], item["code"]))
    # Keep the short list representative when the profile spans multiple areas;
    # otherwise three similarly named programs can crowd out a distinct topic.
    area_support = {}
    for label, criteria in profile_criteria.items():
        for criterion in criteria:
            area_support.setdefault(criterion["area_id"], set()).add(label)
    chosen_codes = set()
    for area_id in sorted(area_support, key=lambda key: (-len(area_support[key]), key)):
        candidate = next((item for item in ranked if area_id in item["_program_areas"] and item["code"] not in chosen_codes), None)
        if candidate:
            chosen_codes.add(candidate["code"])
        if len(chosen_codes) == 3:
            break
    for item in ranked:
        if len(chosen_codes) == 3:
            break
        chosen_codes.add(item["code"])
    shortlisted = [item for item in ranked if item["code"] in chosen_codes]
    suggestions = [{key: value for key, value in item.items() if key not in {"score", "_program_areas"}} for item in shortlisted]
    return {
        "suggestions": suggestions,
        "profile_summary": profile_summary,
        "unmatched_criteria": unmatched_criteria,
        "notice": NOTICE,
        "message": (
            "Các gợi ý được chọn vì có nhóm từ khóa giao nhau với tên chương trình; điều này không xác nhận chương trình phù hợp hơn. Mở nguồn để kiểm tra tên và thông tin tuyển sinh."
            if suggestions
            else "Chưa thấy điểm giao rõ với tên chương trình. Hãy thử lĩnh vực khác hoặc hỏi cán bộ tuyển sinh."
        ),
    }
