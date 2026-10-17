"""Public, source-backed cutoffs for the applicant score reference tool."""

import re
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite

CUTOFF_SOURCE_ID = "hust-cutoffs-2026-table"
METHODS = {
    "THPT": {"label": "Điểm thi tốt nghiệp THPT", "maximum": 30},
    "TSA": {"label": "Đánh giá tư duy (TSA)", "maximum": 100},
    "XTTN 1.2": {"label": "Xét tuyển tài năng 1.2", "maximum": 100},
    "XTTN 1.3": {"label": "Xét tuyển tài năng 1.3", "maximum": 100},
}

IELTS_BONUS = {
    5.0: 1.0,
    5.5: 2.0,
    6.0: 3.0,
    6.5: 4.0,
    7.0: 5.0,
}
IELTS_THPT_SCORE = {5.0: 8.0, 5.5: 8.5, 6.0: 9.0, 6.5: 9.5, 7.0: 10.0}
XTTN_CERTIFICATE_MAX = {"SAT": 1600, "ACT": 36, "A-Level": 30, "AP": 15, "IB": 45}

# HUST's 2026 admissions table lists these combinations. The reference cutoff
# article defines the natural and language/economics groups for THPT scoring.
COMBINATIONS = {
    "A00": {"label": "A00 · Toán, Vật lí, Hóa học", "group": "A00"},
    "A01": {"label": "A01 · Toán, Vật lí, Tiếng Anh", "group": "A00"},
    "B00": {"label": "B00 · Toán, Hóa học, Sinh học", "group": "A00"},
    "D07": {"label": "D07 · Toán, Hóa học, Tiếng Anh", "group": "A00"},
    "K01": {"label": "K01 · Toán, Ngữ văn, Lý/Hóa/Sinh/Tin (có hệ số)", "group": "A00"},
    "D01": {"label": "D01 · Toán, Ngữ văn, Tiếng Anh", "group": "D01"},
    "D04": {"label": "D04 · Toán, Ngữ văn, Tiếng Trung", "group": "D01"},
    "DD2": {"label": "DD2 · Toán, Ngữ văn, Tiếng Hàn", "group": "D01"},
}
COMBINATION_RE = re.compile(r"(?<![A-Z])(?:A00|A01|B00|D01|D04|D07|DD2|K01)(?![A-Z0-9])")

THPT_SUBJECTS = {
    "A00": ("math", "physics", "chemistry"),
    "A01": ("math", "physics", "english"),
    "B00": ("math", "chemistry", "biology"),
    "D01": ("math", "literature", "english"),
    "D04": ("math", "literature", "chinese"),
    "D07": ("math", "chemistry", "english"),
    "DD2": ("math", "literature", "korean"),
}
THPT_PRIORITY_AREA = {"KV1": 0.75, "KV2NT": 0.50, "KV2": 0.25, "KV3": 0.0}
THPT_PRIORITY_GROUP = {"none": 0.0, "UT1": 2.0, "UT2": 1.0}


def _round_score(value):
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _number(value, message, minimum=0, maximum=None):
    if isinstance(value, bool):
        raise ValueError(message)
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(message) from exc
    if not isfinite(number) or number < minimum or (maximum is not None and number > maximum):
        raise ValueError(message)
    return Decimal(str(number))


def ielts_bonus(ielts):
    """HUST 2026 IELTS bonus, returned on the 100-point scale."""
    if ielts is None:
        return Decimal(0)
    band = _number(ielts, "Điểm IELTS phải từ 5.0 đến 9.0.", 5, 9)
    if band < Decimal("5.0"):
        return Decimal(0)
    for threshold in sorted(IELTS_BONUS, reverse=True):
        if band >= Decimal(str(threshold)):
            return Decimal(str(IELTS_BONUS[threshold]))
    return Decimal(0)


def ielts_to_thpt_english(ielts):
    """Convert IELTS Academic to HUST's 2026 English-subject score."""
    band = _number(ielts, "Điểm IELTS phải từ 5.0 đến 9.0.", 5, 9)
    for threshold in sorted(IELTS_THPT_SCORE, reverse=True):
        if band >= Decimal(str(threshold)):
            return Decimal(str(IELTS_THPT_SCORE[threshold]))
    raise ValueError("IELTS từ 5.0 mới được quy đổi điểm tiếng Anh THPT.")


def calculate_alternative_score(method, primary_score, certificate_type=None, ielts=None,
                                achievement_score=0, other_bonus=0, area="KV3", policy_group="none"):
    """Calculate HUST 2026 TSA/XTTN scores from user-entered components."""
    method = str(method).strip()
    bonus100 = ielts_bonus(ielts)
    if method == "TSA":
        tsa = _number(primary_score, "Điểm TSA phải từ 0 đến 100.", 0, 100)
        raw = min(Decimal(100), tsa + bonus100)
        base = raw
        formula = "Min(100, TSA + điểm thưởng IELTS)"
    elif method == "XTTN 1.2":
        if certificate_type not in XTTN_CERTIFICATE_MAX:
            raise ValueError("Hãy chọn loại chứng chỉ XTTN 1.2.")
        cert = _number(primary_score, "Điểm chứng chỉ không hợp lệ.", 0, XTTN_CERTIFICATE_MAX[certificate_type])
        if certificate_type == "SAT":
            total = cert + bonus100 * Decimal(16)
            base = (Decimal(7) * total - Decimal(6150)) / Decimal(60) if total <= 1650 else (total - Decimal(1380)) / Decimal(3)
            formula = "XTTN(SAT) theo bảng HUST 2026 với điểm thưởng IELTS quy đổi theo thang SAT"
        else:
            scale = {"ACT": Decimal("37.8"), "A-Level": Decimal("31.5"), "AP": Decimal("15.75"), "IB": Decimal("47.25")} [certificate_type]
            bonus = bonus100 * Decimal(str(XTTN_CERTIFICATE_MAX[certificate_type])) / Decimal(100)
            base = (cert + bonus) * Decimal(100) / scale
            formula = f"XTTN({certificate_type}) = (chứng chỉ + ĐTNN) × 100 / {scale}"
        base = max(Decimal(0), min(Decimal(100), base))
    elif method == "XTTN 1.3":
        tsa = _number(primary_score, "Điểm TSA phải từ 0 đến 100.", 0, 100)
        achievements = _number(achievement_score, "Điểm thành tích phải từ 0 đến 50.", 0, 50)
        other = _number(other_bonus, "Điểm thưởng khác phải từ 0 đến 10.", 0, 10)
        base = min(Decimal(100), tsa * Decimal(40) / Decimal(60) + achievements + min(Decimal(10), other + bonus100))
        formula = "TSA × 40/60 + điểm thành tích (tối đa 50) + điểm thưởng (tối đa 10)"
    else:
        raise ValueError("Phương thức chưa được hỗ trợ.")
    if area not in THPT_PRIORITY_AREA or policy_group not in THPT_PRIORITY_GROUP:
        raise ValueError("Hãy chọn khu vực và nhóm ưu tiên hợp lệ.")
    priority = (Decimal(str(THPT_PRIORITY_AREA[area])) + Decimal(str(THPT_PRIORITY_GROUP[policy_group]))) * Decimal(100) / Decimal(30)
    if base >= Decimal(75):
        priority = priority * (Decimal(100) - base) / Decimal(25)
    final = min(Decimal(100), base + priority)
    return {
        "method": method,
        "formula": formula,
        "base_score": _round_score(base),
        "ielts_bonus": _round_score(bonus100),
        "priority_score": _round_score(priority),
        "final_score": _round_score(final),
        "maximum": 100,
        "area": area,
        "policy_group": policy_group,
    }


def calculate_thpt_score(combination, scores, area, policy_group, math_coefficient=1, ielts=None):
    """Calculate HUST 2026 THPT score from official subject weights and priority rules."""
    combination = str(combination).upper()
    required = THPT_SUBJECTS.get(combination)
    if combination == "K01":
        required = ("math", "literature", "k01_subject")
    if not required:
        raise ValueError("Tổ hợp chưa được hỗ trợ.")
    if not isinstance(scores, dict) or set(scores) != set(required):
        raise ValueError("Cần nhập đúng các môn thuộc tổ hợp đã chọn.")
    parsed = {}
    for subject, value in scores.items():
        if isinstance(value, bool):
            raise ValueError("Điểm mỗi môn phải từ 0 đến 10.")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Điểm mỗi môn phải từ 0 đến 10.") from exc
        if not isfinite(number) or not 0 <= number <= 10:
            raise ValueError("Điểm mỗi môn phải từ 0 đến 10.")
        parsed[subject] = Decimal(str(number))
    if ielts is not None:
        if combination not in {"A01", "D01", "D07"}:
            raise ValueError("IELTS chỉ được quy đổi cho tổ hợp có môn tiếng Anh.")
        parsed["english"] = ielts_to_thpt_english(ielts)
    if area not in THPT_PRIORITY_AREA or policy_group not in THPT_PRIORITY_GROUP:
        raise ValueError("Hãy chọn khu vực và nhóm ưu tiên hợp lệ.")

    if combination == "K01":
        base_score = (parsed["math"] * 3 + parsed["literature"] + parsed["k01_subject"] * 2) / Decimal(2)
        priority_base = parsed["math"] + parsed["literature"] + parsed["k01_subject"]
        formula = "(Toán × 3 + Ngữ văn + môn K01 × 2) ÷ 2"
    else:
        if math_coefficient not in (1, 2) or isinstance(math_coefficient, bool):
            raise ValueError("Hệ số Toán phải là 1 hoặc 2.")
        if combination not in {"A00", "A01", "B00", "D01", "D07"} and math_coefficient != 1:
            raise ValueError("Tổ hợp này không áp dụng lựa chọn hệ số Toán.")
        priority_base = sum(parsed.values())
        weighted_total = parsed["math"] * math_coefficient + sum(
            value for key, value in parsed.items() if key != "math"
        )
        base_score = weighted_total * Decimal(3) / Decimal(math_coefficient + 2)
        if math_coefficient == 2:
            formula = "(Toán × 2 + hai môn còn lại) × 3/4"
        else:
            formula = "Tổng điểm 3 môn"

    # The 2026 national admission rules explicitly exclude subject coefficients
    # when calculating the 22.50-point priority taper threshold.
    base_priority = Decimal(str(THPT_PRIORITY_AREA[area])) + Decimal(str(THPT_PRIORITY_GROUP[policy_group]))
    adjusted_priority = base_priority
    if priority_base >= Decimal("22.5"):
        adjusted_priority = base_priority * (Decimal(30) - priority_base) / Decimal("7.5")
    final_score = _round_score(base_score + adjusted_priority)
    return {
        "combination": combination,
        "formula": formula,
        "subject_score": _round_score(base_score),
        "priority_base_score": _round_score(priority_base),
        "priority_before_scaling": _round_score(base_priority),
        "priority_score": _round_score(adjusted_priority),
        "final_score": final_score,
        "maximum": 30,
        "area": area,
        "policy_group": policy_group,
    }


def cutoff_for_combination(item, method, combination):
    """Return a source-supported THPT cutoff for an eligible combination."""
    cutoff = item.get("cutoffs", {}).get(method)
    if cutoff is None:
        return None
    if method != "THPT":
        return cutoff if item.get("base_combination") == combination else None
    if combination not in item.get("combinations", []):
        return None
    selected_group = COMBINATIONS[combination]["group"]
    base_group = COMBINATIONS.get(item.get("base_combination"), {}).get("group")
    if selected_group == base_group:
        return cutoff
    if not item.get("has_published_group_offset"):
        return None
    # HUST says natural-group cutoffs are 0.5 higher than language/economics
    # cutoffs for mixed-group programs in economics, education and languages.
    return cutoff + (0.5 if selected_group == "A00" else -0.5)


def thpt_math_coefficients(base_combination, combinations):
    """Return the coefficient shown by HUST's bold main-subject convention.

    The admissions table uses the published base group to mark the main
    subject for the related A00-family or D01-family combinations. K01 has a
    separate formula and therefore is intentionally omitted from this map.
    """
    base_group = COMBINATIONS.get(base_combination, {}).get("group")
    if not base_group:
        return {}
    return {
        combination: 2 if COMBINATIONS[combination]["group"] == base_group else 1
        for combination in combinations
        if combination != "K01" and combination in COMBINATIONS
    }


def build_score_reference(knowledge):
    source = knowledge.documents_by_id.get(CUTOFF_SOURCE_ID)
    if not source or not source.get("official_url", "").startswith("https://"):
        raise ValueError("Nguồn điểm chuẩn chính thức chưa sẵn sàng.")

    program_combinations = {}
    for program in getattr(knowledge, "programs", []):
        code = str(program.get("code", "")).strip().upper()
        declared = set(COMBINATION_RE.findall(str(program.get("methods", "")).upper()))
        if code and declared:
            program_combinations[code.replace("-", "")] = sorted(declared)

    items = []
    for chunk in knowledge.chunks:
        if chunk.get("kind") != "verified_fact" or chunk.get("source_id") != CUTOFF_SOURCE_ID:
            continue
        raw_methods = chunk.get("cutoff_methods")
        if not raw_methods:
            continue
        cutoffs = {}
        for method, value in raw_methods.items():
            rule = METHODS.get(method)
            try:
                score = float(value)
            except (TypeError, ValueError):
                continue
            if rule and isfinite(score) and 0 <= score <= rule["maximum"]:
                cutoffs[method] = score
        if not cutoffs:
            continue
        code = str(chunk.get("program_code", "")).strip().upper()
        name = str(chunk.get("program_name", "")).strip()
        if not code or not name:
            continue
        base_combination = str(chunk.get("base_combination", "")).strip().upper()
        if base_combination not in {"A00", "D01"}:
            continue
        combinations = program_combinations.get(code.replace("-", ""), [])
        if not combinations or base_combination not in combinations:
            raise ValueError(f"Danh sách tổ hợp chưa khớp dữ liệu điểm chuẩn: {code}")
        groups = {COMBINATIONS[combination]["group"] for combination in combinations}
        items.append({
            "code": code,
            "name": name,
            "base_combination": base_combination,
            "combinations": combinations,
            "thpt_math_coefficients": thpt_math_coefficients(base_combination, combinations),
            "thpt_coefficient_source": "Bảng 1 HUST 2026: tổ hợp in đậm là môn chính; K01 dùng công thức riêng",
            "has_published_group_offset": code.startswith(("EM", "ED", "FL")) and len(groups) > 1,
            "cutoffs": cutoffs,
        })

    items.sort(key=lambda item: (item["code"], item["name"]))
    if not items:
        raise ValueError("Chưa có dữ liệu điểm chuẩn hợp lệ.")

    # Keep the historical comparison deliberately narrow: only THPT scores
    # use the same 30-point scale in both cycles. 2025's XTTN/DGTD scores are
    # not interchangeable with the separate 2026 XTTN 1.2/1.3/TSA methods.
    historical_2025 = {}
    for record in getattr(knowledge, "records", {}).values():
        if (record.get("record_type") != "cutoff"
                or record.get("cutoff_year") != 2025
                or record.get("method") != "THPT"
                or record.get("scale") != 30.0
                or not isinstance(record.get("score"), (int, float))):
            continue
        codes = record.get("program_codes") or []
        evidence = record.get("evidence") or {}
        url = evidence.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            continue
        for code in codes:
            normalized_code = str(code).strip().upper().replace("-", "")
            if normalized_code:
                historical_2025[normalized_code] = {
                    "value": float(record["score"]),
                    "source_url": url,
                }
    for item in items:
        item["historical_2025"] = historical_2025.get(item["code"].replace("-", ""))

    return {
        "cycle": 2026,
        "source_checked_on": knowledge.manifest.get("source_checked_on"),
        "source": {"title": source.get("title"), "url": source["official_url"]},
        "historical_source": {
            "title": "Điểm trúng tuyển năm 2025 (tài liệu tuyển sinh HUST)",
            "url": "https://hust.edu.vn/uploads/sys/tuyen-sinh/2023_06/thong-tin-tuyen-sinh-dai-hoc-2026f.pdf",
        },
        "methodology_source": {
            "title": "Công bố phương pháp quy đổi điểm HUST 2026",
            "url": "https://www.hust.edu.vn/vi/news/tin-tuc-su-kien/bach-khoa-ha-noi-cong-bo-chi-tiet-do-lech-diem-to-hop-xet-tuyen-quy-doi-diem-va-du-bao-diem-chuan-nam-2026-655962.html",
        },
        "calculation_rules_source": {
            "title": "Thông tin tuyển sinh đại học chính quy HUST 2026",
            "url": "https://ts.hust.edu.vn/tin-tuc/thong-tin-tuyen-sinh-dai-hoc-chinh-quy-nam-2026",
        },
        "priority_rules_source": {
            "title": "Thông tư 06/2026/TT-BGDĐT · Quy chế tuyển sinh",
            "url": "https://congbao.chinhphu.vn/van-ban/thong-tu-so-06-2026-tt-bgddt-469029/63036.htm",
        },
        "talent_rules_source": {
            "title": "Quy định phương thức xét tuyển tài năng HUST 2026",
            "url": "https://www.hust.edu.vn/uploads/sys/tuyen-sinh/2026_03/qui-dinh-ve-xttn-nam-2026-ky.pdf",
        },
        "language_rules_source": {
            "title": "Hướng dẫn xác thực và quy đổi chứng chỉ ngoại ngữ HUST 2026",
            "url": "https://ts.hust.edu.vn/tin-tuc/huong-dan-dang-ky-xac-thuc-chung-chi-ngoai-ngu-2026",
        },
        "equivalency_tool": {
            "title": "Công cụ quy đổi điểm chính thức HUST 2026",
            "url": "https://tsbkhn.shinyapps.io/QuyDoi-2026BK/",
        },
        "preference_source": {
            "title": "Hướng dẫn sắp xếp nguyện vọng của Bộ GD&ĐT",
            "url": "https://baochinhphu.vn/xet-tuyen-dai-hoc-nam-2026-chinh-thuc-mo-dang-ky-nguyen-vong-dot-1-10226070208290842.htm",
        },
        "methods": [
            {"id": method, **details} for method, details in METHODS.items()
        ],
        "reference_combinations": ["A00", "D01"],
        "combinations": [
            {"id": code, **details}
            for code, details in COMBINATIONS.items()
            if any(code in item["combinations"] for item in items)
        ],
        "combination_methodology_source": {
            "title": "Độ lệch điểm giữa các tổ hợp HUST 2026",
            "url": "https://ts.hust.edu.vn/index.php/tin-tuc/thong-cao-bao-chi-ve-do-lech-giua-cac-to-hop-xet-tuyen-bang-quy-doi-diem-chuan-va-du-bao-muc-diem-trung-tuyen-vao-cac-nganh-cua-dai-hoc-bach-khoa-ha-noi-nam-2026",
        },
        "items": items,
        "notice": (
            "Điểm chuẩn mỗi năm thay đổi. Các mốc cũ chỉ giúp bạn tham khảo, không dự báo "
            "kết quả năm tới. Công cụ hỗ trợ tính từ TSA, chứng chỉ XTTN và IELTS theo "
            "công thức HUST 2026; vẫn cần đối chiếu điều kiện và minh chứng xác thực chính thức."
        ),
    }
