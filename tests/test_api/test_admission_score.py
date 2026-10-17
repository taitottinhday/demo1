import pytest
from fastapi import HTTPException

from src.api.routes import THPTScoreInput, calculate_program_thpt_score
from src.services.admission_score import build_score_reference, calculate_alternative_score, calculate_thpt_score, cutoff_for_combination


def test_tsa_and_ielts_use_hust_2026_bonus_and_priority_formula():
    result = calculate_alternative_score("TSA", 80, ielts=7.0, area="KV3", policy_group="none")

    assert result["ielts_bonus"] == 5.0
    assert result["base_score"] == 85.0
    assert result["final_score"] == 85.0


def test_xttn_12_sat_uses_official_piecewise_formula():
    result = calculate_alternative_score("XTTN 1.2", 1600, "SAT", ielts=7.0)

    assert result["base_score"] == 100.0
    assert result["final_score"] == 100.0


def test_xttn_13_uses_tsa_achievement_and_bonus_caps():
    result = calculate_alternative_score("XTTN 1.3", 60, ielts=7.0, achievement_score=50, other_bonus=10)

    assert result["base_score"] == 100.0


def test_thpt_ielts_uses_hust_2026_english_conversion():
    result = calculate_thpt_score(
        "D01", {"math": 8, "literature": 8, "english": 0}, "KV3", "none", 1, 6.5
    )

    assert result["subject_score"] == 25.5


def test_score_reference_exposes_only_hust_combinations_and_program_eligibility(knowledge):
    result = build_score_reference(knowledge)

    assert len(result["items"]) == 68
    assert {item["id"] for item in result["combinations"]} == {
        "A00", "A01", "B00", "D01", "D04", "D07", "DD2", "K01"
    }
    by_code = {item["code"]: item for item in result["items"]}
    assert {"A00", "A01", "K01"}.issubset(by_code["ED2"]["combinations"])
    assert "D01" in by_code["FL4"]["combinations"]
    assert "A00" not in by_code["FL4"]["combinations"]
    assert by_code["EM1"]["has_published_group_offset"] is True
    assert by_code["TROY-IT"]["has_published_group_offset"] is False
    assert all(item["base_combination"] in item["combinations"] for item in result["items"])
    assert all(set(item["cutoffs"]) == {"THPT", "TSA", "XTTN 1.2", "XTTN 1.3"} for item in result["items"])


def test_score_reference_suggests_math_coefficient_from_program_base_group(knowledge):
    result = build_score_reference(knowledge)
    by_code = {item["code"]: item for item in result["items"]}

    # EM1 is a D01-base mixed-group program; the D01 family is the bold/main
    # subject group while A00-family combinations use coefficient 1.
    assert by_code["EM1"]["thpt_math_coefficients"]["D01"] == 2
    assert by_code["EM1"]["thpt_math_coefficients"]["A00"] == 1
    # K01 keeps its separate three-subject formula and is not presented as a
    # selectable Math coefficient.
    assert "K01" not in by_code["EM1"]["thpt_math_coefficients"]
    assert by_code["IT1"]["thpt_math_coefficients"]["A00"] == 2


def test_score_reference_includes_historical_thpt_only_when_same_scale_is_available(knowledge):
    result = build_score_reference(knowledge)
    by_code = {item["code"]: item for item in result["items"]}

    assert by_code["BF1"]["historical_2025"]["value"] == 23.02
    assert by_code["BF1"]["historical_2025"]["source_url"].startswith("https://")
    assert result["historical_source"]["url"].startswith("https://")
    assert all(set(item["cutoffs"]) == {"THPT", "TSA", "XTTN 1.2", "XTTN 1.3"} for item in result["items"])


def test_thpt_cross_group_cutoff_uses_published_half_point_adjustment():
    item = {"base_combination": "D01", "combinations": ["A00", "D01"], "has_published_group_offset": True, "cutoffs": {"THPT": 24.0}}

    assert cutoff_for_combination(item, "THPT", "A00") == 24.5
    assert cutoff_for_combination(item, "THPT", "D01") == 24.0
    assert cutoff_for_combination(item, "THPT", "A01") is None

    reverse = {"base_combination": "A00", "combinations": ["A00", "D01"], "has_published_group_offset": True, "cutoffs": {"THPT": 24.0}}
    assert cutoff_for_combination(reverse, "THPT", "D01") == 23.5


def test_unpublished_cross_group_offset_is_not_invented():
    item = {"base_combination": "D01", "combinations": ["A00", "D01"], "has_published_group_offset": False, "cutoffs": {"THPT": 24.0}}

    assert cutoff_for_combination(item, "THPT", "A00") is None


def test_non_thpt_method_keeps_official_reference_group_without_combination_shift():
    item = {"base_combination": "D01", "combinations": ["A00", "D01"], "cutoffs": {"TSA": 60.0}}

    assert cutoff_for_combination(item, "TSA", "D01") == 60.0
    assert cutoff_for_combination(item, "TSA", "A00") is None


def test_thpt_calculation_applies_math_weight_and_priority_scaling():
    result = calculate_thpt_score(
        "A00", {"math": 8, "physics": 9, "chemistry": 10}, "KV1", "UT1", 2
    )

    assert result["subject_score"] == 26.25
    assert result["priority_base_score"] == 27
    assert result["priority_before_scaling"] == 2.75
    assert result["priority_score"] == 1.10
    assert result["final_score"] == 27.35


def test_thpt_calculation_handles_unweighted_combination_and_k01_formula():
    d04 = calculate_thpt_score(
        "D04", {"math": 8, "literature": 9, "chinese": 10}, "KV3", "none"
    )
    d01 = calculate_thpt_score(
        "D01", {"math": 8, "literature": 9, "english": 10}, "KV3", "none", 2
    )
    dd2 = calculate_thpt_score(
        "DD2", {"math": 8, "literature": 9, "korean": 10}, "KV3", "none"
    )
    k01 = calculate_thpt_score(
        "K01", {"math": 8, "literature": 9, "k01_subject": 10}, "KV3", "none"
    )

    assert d04["subject_score"] == 27
    assert d01["subject_score"] == 26.25
    assert dd2["subject_score"] == 27
    assert k01["subject_score"] == 26.5


def test_thpt_math_coefficient_is_explicit_and_scales_only_the_subject_score():
    scores = {"math": 8, "physics": 9, "chemistry": 10}
    all_equal = calculate_thpt_score("A00", scores, "KV3", "none", 1)
    math_doubled = calculate_thpt_score("A00", scores, "KV3", "none", 2)

    assert all_equal["subject_score"] == 27
    assert all_equal["priority_base_score"] == math_doubled["priority_base_score"] == 27
    assert math_doubled["subject_score"] == 26.25
    with pytest.raises(ValueError, match="không áp dụng"):
        calculate_thpt_score("D04", {"math": 8, "literature": 9, "chinese": 10}, "KV3", "none", 2)


def test_thpt_priority_taper_uses_unweighted_sum_at_the_22_5_boundary():
    at_threshold = calculate_thpt_score(
        "A00", {"math": 7.5, "physics": 7.5, "chemistry": 7.5}, "KV1", "none"
    )
    below_threshold = calculate_thpt_score(
        "A00", {"math": 7.5, "physics": 7.49, "chemistry": 7.5}, "KV1", "none"
    )

    assert at_threshold["priority_base_score"] == 22.5
    assert at_threshold["priority_score"] == 0.75
    assert below_threshold["priority_base_score"] == 22.49
    assert below_threshold["priority_score"] == 0.75


def test_thpt_final_score_rounds_only_after_subject_and_priority_are_added():
    result = calculate_thpt_score(
        "A00", {"math": 5.3, "physics": 9.98, "chemistry": 7.23}, "KV1", "UT1", 2
    )

    assert result["subject_score"] == 20.86
    assert result["priority_score"] == 2.75
    assert result["final_score"] == 23.60


def test_thpt_calculation_rejects_missing_or_out_of_range_subject_scores():
    with pytest.raises(ValueError, match="đúng các môn"):
        calculate_thpt_score("A00", {"math": 8, "physics": 9}, "KV3", "none")
    with pytest.raises(ValueError, match="từ 0 đến 10"):
        calculate_thpt_score("A00", {"math": 10.1, "physics": 9, "chemistry": 8}, "KV3", "none")


def test_thpt_calculation_api_returns_breakdown_and_rejects_invalid_values():
    response = calculate_program_thpt_score(THPTScoreInput(
        combination="K01",
        scores={"math": 8, "literature": 9, "k01_subject": 10},
        area="KV2NT",
        policy_group="UT2",
    ))
    assert response["subject_score"] == 26.5
    assert response["priority_score"] == 0.6
    assert response["final_score"] == 27.1

    weighted = calculate_program_thpt_score(THPTScoreInput(
        combination="A00",
        scores={"math": 8, "physics": 9, "chemistry": 10},
        area="KV3",
        policy_group="none",
        math_coefficient=2,
    ))
    assert weighted["formula"] == "(Toán × 2 + hai môn còn lại) × 3/4"
    assert weighted["final_score"] == 26.25

    invalid = THPTScoreInput(
        combination="A00",
        scores={"math": 11, "physics": 9, "chemistry": 8},
        area="KV1",
        policy_group="UT1",
    )
    with pytest.raises(HTTPException) as exc_info:
        calculate_program_thpt_score(invalid)
    assert exc_info.value.status_code == 422
