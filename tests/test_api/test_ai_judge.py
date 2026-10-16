import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from scripts.judge_answers import evidence_for, judge_report, metrics
from src.config import Settings
from src.services.admissions import Admissions
from src.services.store import Store


@pytest.fixture
def report(knowledge):
    saved = json.loads(Path("eval/results/golden-report.json").read_text(encoding="utf-8"))
    saved["rows"] = copy.deepcopy(saved["rows"][:3])
    # Bind the legacy fixture's unchanged evidence to the current ingestion IDs.
    # Production judging intentionally rejects stale IDs instead of remapping.
    for row in saved["rows"]:
        for source in row["sources"]:
            match = next((c for c in knowledge.chunks
                         if c["source_id"] == source["source_id"]
                         and source["excerpt"] == c.get("evidence")), None)
            if match:
                source["id"] = match["id"]
    saved["source_version"] = knowledge.version
    saved["retrieval_version"] = knowledge.version
    return saved


def fake_judge(content=None):
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=content or json.dumps({
            "verdict": "correct", "citations_supported": True, "answers_question": True,
            "reference_consistent": True, "reason": "Supported by the supplied evidence.",
        })))], usage=SimpleNamespace(total_tokens=11),
    )
    return client


@pytest.mark.asyncio
async def test_judge_budget_and_partial_coverage_never_claim_full_accuracy(knowledge, report):
    client = fake_judge()
    report["rows"][2]["judge"] = {"verdict": "correct"}
    with patch("scripts.judge_answers.AsyncOpenAI", return_value=client) as factory:
        result = await judge_report(report, knowledge, Settings(_env_file=None, deepseek_api_key="test"), 1)
    assert result["judge_run"]["calls"] == 1
    assert result["judge_run"]["tokens_known"] == 11
    assert client.chat.completions.create.await_count == 1
    assert factory.call_args.kwargs["max_retries"] == 0
    assert result["judge_coverage"] == 33.33
    assert result["accuracy_judge"] is None
    assert result["kpi_verified"] is False
    assert result["rows"][2]["judge_status"] == "call_limit"
    assert "judge" not in result["rows"][2]


@pytest.mark.asyncio
async def test_judge_reuses_only_same_response_source_model_and_rubric(knowledge, report):
    settings = Settings(_env_file=None, deepseek_api_key="test")
    original = copy.deepcopy(report)
    with patch("scripts.judge_answers.AsyncOpenAI", return_value=fake_judge()):
        saved = await judge_report(report, knowledge, settings, 1)
    client = fake_judge()
    with patch("scripts.judge_answers.AsyncOpenAI", return_value=client):
        result = await judge_report(copy.deepcopy(original), knowledge, settings, 1, reuse=copy.deepcopy(saved))
    assert result["rows"][0]["judge_status"] == "cached"
    assert result["judge_run"]["cache_hits"] == 1
    assert client.chat.completions.create.await_count == 1
    saved["judge_run"]["model"] = "different-model"
    with patch("scripts.judge_answers.AsyncOpenAI", return_value=fake_judge()):
        result = await judge_report(original, knowledge, settings, 1, reuse=saved)
    assert result["judge_run"]["cache_hits"] == 0


@pytest.mark.asyncio
async def test_judge_rejects_noncanonical_question_before_any_provider_call(knowledge, report):
    report["rows"][0]["question"] = "Private conversation must not be exported"
    with patch("scripts.judge_answers.AsyncOpenAI") as factory, pytest.raises(ValueError, match="canonical"):
        await judge_report(report, knowledge, Settings(_env_file=None, deepseek_api_key="test"), 1)
    factory.assert_not_called()


def test_judge_refuses_forged_source_and_invalid_citation(knowledge, report):
    row = report["rows"][0]
    assert evidence_for(row, knowledge)
    row["sources"][0]["excerpt"] = "Forged evidence, absent from the validated corpus."
    assert evidence_for(row, knowledge) is None
    row = report["rows"][1]
    row["response"] += " [999]"
    assert evidence_for(row, knowledge) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("content,status", [
    ("not JSON", "invalid_json"),
    ('{"verdict":"correct","citations_supported":false,"answers_question":true,'
     '"reference_consistent":true,"reason":"Contradictory verdict."}', "inconsistent_verdict"),
])
async def test_invalid_judge_output_is_not_a_pass(knowledge, report, content, status):
    with patch("scripts.judge_answers.AsyncOpenAI", return_value=fake_judge(content)):
        result = await judge_report(report, knowledge, Settings(_env_file=None, deepseek_api_key="test"), 1)
    assert result["rows"][0]["judge_status"] == status
    assert result["judge_coverage"] == 0
    assert result["accuracy_judge"] is None


def test_uncertain_verdict_counts_against_automated_accuracy():
    result = metrics({"rows": [
        {"actual_kind": "answered", "judge": {"verdict": "correct"}},
        {"actual_kind": "answered", "judge": {"verdict": "uncertain"}},
    ]})
    assert result["judge_coverage"] == 100
    assert result["accuracy_judge"] == 50
    assert result["judge_uncertain"] == 1
    assert result["kpi_verified"] is False


def test_human_accuracy_requires_named_reviewer_and_complete_answer_coverage():
    report = {"rows": [
        {"actual_kind": "answered", "human_correct": True, "reviewer": ""},
        {"actual_kind": "answered", "human_correct": False, "reviewer": "staff-reviewer"},
    ]}
    assert metrics(report)["human_coverage"] == 50
    assert metrics(report)["accuracy_human"] is None
    report["rows"][0]["reviewer"] = "staff-reviewer"
    assert metrics(report)["accuracy_human"] == 50
    assert metrics(report)["kpi_verified"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [
    "Điểm chuẩn THPT năm 2026 của IT1 là 27,29.",
    "Điểm chuẩn THPT năm 2026 của IT2 là 29,27.",
])
async def test_generation_rejects_decimal_reversal_and_wrong_program(knowledge, tmp_path, text):
    settings = Settings(_env_file=None, llm_provider="deepseek", deepseek_api_key="test")
    service = Admissions(knowledge, Store(tmp_path / "numeric.db"), settings)
    quote = "Điểm chuẩn THPT năm 2026 của IT1 là 29,27."
    client = AsyncMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps({
            "supported": True, "claims": [{"text": text, "source": 1, "quote": quote}],
        })))], usage=SimpleNamespace(total_tokens=20),
    )
    with patch("src.services.admissions.AsyncOpenAI", return_value=client):
        usage = {"tokens": 0}
        assert await service.generate("Điểm chuẩn IT1?", [{"text": quote}], [], usage=usage) is None
        assert usage["tokens"] == 20


@pytest.mark.asyncio
async def test_judge_invalid_budget_never_opens_client(knowledge, report):
    with patch("scripts.judge_answers.AsyncOpenAI") as factory, pytest.raises(ValueError, match="max_calls"):
        await judge_report(report, knowledge, Settings(_env_file=None), 0)
    factory.assert_not_called()


@pytest.mark.asyncio
async def test_evidenced_academic_year_is_allowed_without_opening_future_admissions(knowledge, tmp_path):
    service = Admissions(knowledge, Store(tmp_path / "academic.db"), Settings(
        _env_file=None, llm_provider="deepseek", deepseek_api_key="test",
    ))
    quote = "Quy định có hiệu lực từ học kỳ 1 năm học 2026–2027 với sinh viên chính quy từ khóa K71."
    client = AsyncMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps({
            "supported": True, "claims": [{"text": quote, "source": 1, "quote": quote}],
        })))], usage=SimpleNamespace(total_tokens=20),
    )
    with patch("src.services.admissions.AsyncOpenAI", return_value=client):
        result = await service.generate("Quy định áp dụng khi nào?", [
            {"text": quote, "source_id": "hust-english-policy-k71"},
        ], [])
    assert result and "2026–2027" in result["response"]
    assert service.guard("Điều kiện tuyển sinh năm 2027 là gì?")


@pytest.mark.asyncio
async def test_quote_validation_preserves_vietnamese_accents(knowledge, tmp_path):
    service = Admissions(knowledge, Store(tmp_path / "accents.db"), Settings(
        _env_file=None, llm_provider="deepseek", deepseek_api_key="test",
    ))
    client = AsyncMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps({
            "supported": True, "claims": [{"text": "Học phí IT1: 700.", "source": 1,
                                           "quote": "Hoc phi IT1: 700."}],
        })))], usage=SimpleNamespace(total_tokens=20),
    )
    with patch("src.services.admissions.AsyncOpenAI", return_value=client):
        assert await service.generate("Học phí IT1?", [{"text": "Học phí IT1: 700."}], []) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["rejected", "provider", "budget"])
async def test_verified_fact_fallback_preserves_source_and_call_budget(knowledge, tmp_path, failure):
    service = Admissions(knowledge, Store(tmp_path / "fallback.db"), Settings(
        _env_file=None, answer_mode="llm", llm_provider="deepseek", deepseek_api_key="test",
        llm_daily_limit=0 if failure == "budget" else 5,
    ))

    async def rejected(*args, usage):
        usage["tokens"] = 30
        if failure == "provider":
            raise TimeoutError("Private provider details")
        return None

    service.generate = AsyncMock(side_effect=rejected)
    answer = await service.answer("Học kỳ hè có học phí như học kỳ chính không?")
    assert answer["kind"] == "answered" and answer["mode"] == "extractive"
    assert answer["reason"].startswith("verified_facts_")
    assert "1,5" in answer["response"]
    assert answer["sources"][0]["source_id"] == "hust-tuition-2026-2027"
    assert answer["tokens"] == (0 if failure == "budget" else 30)
    assert service.generate.await_count == (0 if failure == "budget" else 1)


@pytest.mark.asyncio
async def test_concurrent_requests_cannot_exceed_paid_call_limit(knowledge, tmp_path):
    service = Admissions(knowledge, Store(tmp_path / "parallel.db"), Settings(
        _env_file=None, answer_mode="llm", llm_provider="deepseek", deepseek_api_key="test", llm_daily_limit=2,
    ))

    async def generate(*args, **kwargs):
        await asyncio.sleep(0.05)
        return {"response": "IT1: Khoa học máy tính. [1]", "tokens": 10}

    service.generate = AsyncMock(side_effect=generate)
    results = await asyncio.gather(*[service.answer("Giới thiệu chương trình IT1") for _ in range(8)])
    assert service.generate.await_count == 2
    assert sum(r["reason"] == "budget_limit" for r in results) == 6
