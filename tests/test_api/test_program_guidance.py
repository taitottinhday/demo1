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
    assert "chưa mô tả đầy đủ" in data["notice"]


def test_guidance_does_not_echo_or_persist_free_text(guidance_runtime):
    request, store, _ = guidance_runtime
    private_note = "unique-private-guidance-93c7f5"
    result = program_guidance(
        ProgramGuidanceInput(strengths_note=private_note, interests_note="Thích AI và phân tích dữ liệu"),
        request,
        {"id": "candidate-private-test"},
    )

    assert private_note not in json.dumps(result, ensure_ascii=False)
    assert store.messages("candidate-private-test") == []
    assert store.tickets("candidate-private-test") == []


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
