import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.api.routes import program_guidance, program_guidance_options
from src.config import Settings
from src.models.schemas import ProgramGuidanceInput, ProgramGuidanceResponse
from src.services.store import Store


@pytest.fixture
def guidance_runtime(tmp_path, knowledge):
    store = Store(tmp_path / "program-guidance.db")
    settings = Settings(_env_file=None, answer_mode="extractive", app_env="test")
    runtime = {"settings": settings, "store": store, "knowledge": knowledge}
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(runtime=runtime)))
    return request, store, knowledge


def test_guidance_options_come_from_loaded_program_catalog(guidance_runtime):
    request, _, _ = guidance_runtime
    data = program_guidance_options(request)

    ids = {area["id"] for area in data["areas"]}
    assert "computing" in ids
    assert "data_ai" in ids
    assert data["notice"]


def test_guidance_returns_up_to_three_source_linked_programs(guidance_runtime):
    request, _, knowledge = guidance_runtime
    result = program_guidance(
        ProgramGuidanceInput(strengths=["computing"], interests=["data_ai"]), request, {"id": "candidate-test"}
    )
    data = ProgramGuidanceResponse.model_validate(result).model_dump()

    assert 0 < len(data["suggestions"]) <= 3
    known_codes = {program["code"] for program in knowledge.programs}
    for suggestion in data["suggestions"]:
        assert suggestion["code"] in known_codes
        assert suggestion["badge"]
        assert suggestion["reasons"]
        assert suggestion["source"]["page"] > 0
        assert suggestion["source"]["local_url"].startswith("/api/v1/source/pdf?source_id=")
        assert "#page=" in suggestion["source"]["local_url"]
        assert "score" not in suggestion
        assert "percent" not in json.dumps(suggestion, ensure_ascii=False).lower()
    assert "tên chương trình" in data["notice"].lower()
    assert "không gửi tới ai bên ngoài" in data["notice"].lower()


def test_guidance_summarizes_free_text_without_saving_it_to_chat_or_ticket(guidance_runtime):
    request, store, _ = guidance_runtime
    private_note = "unique-private-guidance-93c7f5"
    result = program_guidance(
        ProgramGuidanceInput(strengths_note=private_note, interests_note="Thích AI và phân tích dữ liệu"),
        request,
        {"id": "candidate-private-test"},
    )

    assert private_note in result["profile_summary"]["strengths"]
    assert private_note not in json.dumps(store.messages("candidate-private-test"), ensure_ascii=False)
    assert store.messages("candidate-private-test") == []
    assert store.tickets("candidate-private-test") == []


def test_example_profile_has_specific_title_linked_reasons_for_each_suggested_program(guidance_runtime):
    request, _, knowledge = guidance_runtime
    profile = ProgramGuidanceInput(
        strengths_note="Toán, lập trình Python và giải thuật",
        interests_note="Giải bài toán, lập trình phần mềm",
        career_direction="AI và phần mềm",
        improvements_note="Giao tiếp và thuyết trình",
        priorities="Chương trình thiên về phần mềm",
    )
    data = ProgramGuidanceResponse.model_validate(
        program_guidance(profile, request, {"id": "candidate-guidance-example"})
    ).model_dump()

    assert data["profile_summary"] == {
        "strengths": ["Toán, lập trình Python và giải thuật"],
        "interests": ["Giải bài toán, lập trình phần mềm"],
        "direction": ["AI và phần mềm"],
        "development_goals": ["Giao tiếp và thuyết trình"],
        "priorities": ["Chương trình thiên về phần mềm"],
    }
    programs = {item["code"]: item for item in knowledge.programs}
    for suggestion in data["suggestions"]:
        assert suggestion["name"] == programs[suggestion["code"]]["name"]
        assert suggestion["criteria_matches"]
        for match in suggestion["criteria_matches"]:
            assert match["criteria"]
            assert match["program_name_terms"]
            assert all(term.casefold() in suggestion["name"].casefold() for term in match["program_name_terms"])
        assert "Chưa đủ dữ liệu" in " ".join(suggestion["insufficient_data"])
        assert "score" not in suggestion
        assert "percent" not in json.dumps(suggestion, ensure_ascii=False).lower()

    by_code = {item["code"]: item for item in data["suggestions"]}
    assert {"ETE9", "IT1", "ITE10"}.issubset(by_code)
    assert any("giải thuật" in value.lower() for match in by_code["IT1"]["criteria_matches"] for value in match["criteria"])
    assert any("ai" in value.lower() for match in by_code["ITE10"]["criteria_matches"] for value in match["criteria"])
    assert any(item["group"] == "Mục tiêu phát triển" for item in data["unmatched_criteria"])
    assert any("không được dùng để xếp hạng" in item["message"] for item in data["unmatched_criteria"])


def test_guidance_handles_missing_groups_and_priority_without_catalog_evidence(guidance_runtime):
    request, _, _ = guidance_runtime
    no_optional_groups = ProgramGuidanceInput(
        interests_note="lập trình phần mềm",
        improvements_note="Giao tiếp và thuyết trình",
    )
    data = program_guidance(no_optional_groups, request, {"id": "candidate-guidance-missing-groups"})

    assert data["suggestions"]
    assert data["profile_summary"]["strengths"] == []
    assert data["profile_summary"]["direction"] == []
    assert data["profile_summary"]["priorities"] == []
    assert data["profile_summary"]["development_goals"] == ["Giao tiếp và thuyết trình"]
    assert any(item["group"] == "Mục tiêu phát triển" for item in data["unmatched_criteria"])

    unsupported_priority = ProgramGuidanceInput(priorities="Cơ hội thực tập ở nước ngoài")
    empty = program_guidance(unsupported_priority, request, {"id": "candidate-guidance-unsupported-priority"})
    assert empty["suggestions"] == []
    assert empty["profile_summary"]["priorities"] == ["Cơ hội thực tập ở nước ngoài"]
    assert any(item["group"] == "Tiêu chí ưu tiên" and "Chưa đủ dữ liệu" in item["message"] for item in empty["unmatched_criteria"])

    goals_only = ProgramGuidanceInput(improvements_note="Giao tiếp và thuyết trình")
    goals_result = program_guidance(goals_only, request, {"id": "candidate-guidance-goals-only"})
    assert goals_result["suggestions"] == []
    assert goals_result["profile_summary"]["development_goals"] == ["Giao tiếp và thuyết trình"]
    assert any("không được dùng để xếp hạng" in item["message"] for item in goals_result["unmatched_criteria"])


@pytest.mark.parametrize(
    ("updates", "summary_key"),
    [
        ({"strengths": [], "strengths_note": ""}, "strengths"),
        ({"interests": [], "interests_note": ""}, "interests"),
        ({"career_direction": ""}, "direction"),
        ({"improvements": [], "improvements_note": ""}, "development_goals"),
        ({"priorities": ""}, "priorities"),
    ],
)
def test_guidance_can_leave_any_single_profile_group_blank(guidance_runtime, updates, summary_key):
    request, _, _ = guidance_runtime
    base = ProgramGuidanceInput(
        strengths=["computing"],
        interests=["data_ai"],
        career_direction="AI",
        improvements=["mechanical"],
        priorities="phần mềm",
    )
    profile = base.model_copy(update=updates)
    data = program_guidance(profile, request, {"id": f"candidate-guidance-blank-{summary_key}"})

    assert data["suggestions"]
    assert data["profile_summary"][summary_key] == []


def test_guidance_understands_common_school_subjects_without_scoring_weakness_as_a_penalty(guidance_runtime):
    request, _, _ = guidance_runtime
    strength_only = program_guidance(
        ProgramGuidanceInput(strengths_note="Mình khá môn Toán"), request, {"id": "candidate-subject-base"}
    )
    result = program_guidance(
        ProgramGuidanceInput(strengths_note="Mình khá môn Toán", improvements=["data_ai"]),
        request,
        {"id": "candidate-subject-test"},
    )

    assert result["suggestions"]
    assert any("Dữ liệu và trí tuệ nhân tạo" in item["matched_strengths"] for item in result["suggestions"])
    assert [item["code"] for item in result["suggestions"]] == [item["code"] for item in strength_only["suggestions"]]


def test_empty_guidance_profile_returns_helpful_empty_result(guidance_runtime):
    request, _, _ = guidance_runtime
    result = program_guidance(ProgramGuidanceInput(), request, {"id": "candidate-empty-test"})

    assert result["suggestions"] == []
    assert "chưa có chủ đề" in result["message"].lower()


def test_guidance_schema_rejects_identity_unknown_category_and_oversized_input():
    cases = [
        {"name": "Nguyễn Văn A", "strengths": ["computing"]},
        {"strengths": ["unknown_area"]},
        {"strengths": ["computing", "data_ai", "electrical", "mechanical", "languages_media"]},
        {"strengths_note": "x" * 401},
    ]

    for payload in cases:
        with pytest.raises(ValidationError):
            ProgramGuidanceInput.model_validate(payload)


def test_guidance_rate_limit_is_applied_per_anonymous_session(guidance_runtime):
    request, _, _ = guidance_runtime
    row = {"id": "candidate-rate-limit-test"}
    for _ in range(8):
        program_guidance(ProgramGuidanceInput(strengths=["computing"]), request, row)

    with pytest.raises(HTTPException) as error:
        program_guidance(ProgramGuidanceInput(strengths=["computing"]), request, row)

    assert error.value.status_code == 429
