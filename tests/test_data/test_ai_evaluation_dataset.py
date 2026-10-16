import hashlib
import json
from pathlib import Path

import pytest

from src.config import Settings
from src.services.admissions import Admissions
from src.services.knowledge import canonical_quote
from src.services.store import Store


def review_cases():
    return [json.loads(line) for line in Path("eval/admissions_review.jsonl").read_text(encoding="utf-8").splitlines()]


def test_review_dataset_has_balanced_draft_cases_and_review_fields():
    cases = review_cases()
    assert len(cases) == 130
    assert sum(not case["safety"] for case in cases) == 100
    assert sum(case["safety"] for case in cases) == 30
    assert len({case["id"] for case in cases}) == len({case["question"] for case in cases}) == 130
    for case in cases:
        assert case["expected_kind"] == ("fallback" if case["safety"] else "answered")
        assert case["expected_answer"] and case["split"] == "review_draft"
        assert type(case["label_reviewed"]) is bool
        if case["label_reviewed"]:
            assert case["label_reviewer"].strip()
        assert bool(case["evidence"]) is not case["safety"]
        assert case["source_ids"] == [e["source_id"] for e in case["evidence"]]


def test_review_evidence_resolves_to_exact_versioned_source_material(knowledge):
    facts_path = Path("data/normalized/admissions_facts_2026.json")
    facts = json.loads(facts_path.read_text(encoding="utf-8"))["facts"]
    capture_version = hashlib.sha256(facts_path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    normalized = [json.loads(line) for line in Path("data/processed/chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    mapping = {s["source_id"]: s["runtime_source_id"] for s in json.loads(
        Path("data/manifests/sources.json").read_text(encoding="utf-8"))["sources"]}
    for case in review_cases():
        for e in case["evidence"]:
            source = knowledge.documents_by_id[e["source_id"]]
            assert e["url"] == source["official_url"]
            if source["type"] == "pdf":
                assert e["source_version"] == source["version"]
                assert 1 <= e["page"] <= e["end_page"] <= source["pages"]
                assert e["source_version_kind"] == "pdf_bytes"
            else:
                assert e["page"] is None and e["source_version_kind"] == "curated_web_capture"
                assert e["source_version"] == capture_version
            if e["evidence_type"] == "native":
                assert any(mapping[c["source_id"]] == e["source_id"]
                           and canonical_quote(c["text"]) == canonical_quote(e["quote"])
                           and c["answer_eligible"] and not c["historical"] for c in normalized)
            elif e["evidence_type"] == "curated_source_fact":
                assert any(f["source_id"] == e["source_id"] and f["evidence"] == e["quote"] for f in facts)
            else:
                assert e["evidence_type"] == "parsed_pdf_table_row"
                assert any(c["source_id"] == e["source_id"] and c["evidence"] == e["quote"]
                           and c["page"] == e["page"] for c in knowledge.chunks)


@pytest.mark.asyncio
async def test_review_safety_cases_never_emit_sourced_answers(knowledge, tmp_path):
    service = Admissions(knowledge, Store(tmp_path / "review-safety.db"), Settings(_env_file=None))
    for case in review_cases():
        if case["safety"]:
            result = await service.answer(case["question"])
            assert result["kind"] == "fallback", case["id"]
            assert result["sources"] == [], case["id"]
