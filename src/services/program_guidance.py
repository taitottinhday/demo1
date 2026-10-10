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
    "Kết quả đối chiếu chủ đề bạn chọn với tên chương trình trong tài liệu HUST 2026. Tài liệu chưa mô tả đầy đủ nội dung học hoặc nghề nghiệp; "
    "đây không phải đánh giá năng lực hay dự đoán trúng tuyển. Thông tin không được gửi tới dịch vụ AI bên ngoài."
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

    Improvement areas are returned only as considerations and never lower a rank.
    Free-text fields are inspected in memory and are never echoed or persisted.
    """
    allowed_areas = {area["id"] for area in AREAS}
    strengths = set(profile.strengths) & allowed_areas
    strengths.update(_text_areas(profile.strengths_note))
    interests = set(profile.interests) & allowed_areas
    for value in (profile.interests_note, profile.career_direction, profile.priorities):
        interests.update(_text_areas(value))
    improvements = set(profile.improvements) & allowed_areas
    improvements.update(_text_areas(profile.improvements_note))

    selected = strengths | interests
    if not selected:
        return {
            "suggestions": [],
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
        program_areas = {
            area["id"] for area in AREAS if any(_contains(name, _plain(term)) for term in area["program_terms"])
        }
        matched_strengths = sorted(strengths & program_areas)
        matched_interests = sorted(interests & program_areas)
        score = 2 * len(matched_strengths) + 3 * len(matched_interests)
        chunk = chunks_by_code.get(code)
        if score <= 0 or chunk is None:
            continue

        reasons = []
        if matched_interests:
            reasons.append("Có điểm giao với lĩnh vực bạn quan tâm.")
        if matched_strengths:
            reasons.append("Có điểm giao với thế mạnh bạn chọn.")
        matched_improvements = sorted(improvements & program_areas)
        considerations = []
        if matched_improvements:
            labels = ", ".join(AREA_BY_ID[key]["label"] for key in matched_improvements)
            considerations.append(
                f"Muốn phát triển: {labels}. Tài liệu chưa nêu rõ mức độ đào tạo."
            )
        if profile.improvements or profile.improvements_note:
            considerations.append("Mục tiêu phát triển không làm giảm mức gợi ý.")

        if matched_interests and matched_strengths:
            badge = "Giao với sở thích + thế mạnh"
        elif matched_interests:
            badge = "Giao với sở thích"
        else:
            badge = "Giao với thế mạnh"

        citation = knowledge.citation(chunk)
        ranked.append(
            {
                "score": score,
                "code": code,
                "name": program["name"],
                "badge": badge,
                "reasons": reasons,
                "matched_strengths": [AREA_BY_ID[key]["label"] for key in matched_strengths],
                "matched_interests": [AREA_BY_ID[key]["label"] for key in matched_interests],
                "considerations": considerations,
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
    suggestions = [{key: value for key, value in item.items() if key != "score"} for item in ranked[:3]]
    return {
        "suggestions": suggestions,
        "notice": NOTICE,
        "message": (
            "Các gợi ý dựa trên điểm giao giữa chủ đề bạn chọn và tên chương trình. Mở tài liệu để tìm hiểu thêm."
            if suggestions
            else "Chưa thấy điểm giao rõ với tên chương trình. Hãy thử lĩnh vực khác hoặc hỏi cán bộ tuyển sinh."
        ),
    }
