"""Integrity checks for the normalized HUST admissions data corpus."""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import pymupdf


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def test_source_catalog_has_unique_official_sources_and_valid_local_files():
    catalog = _json(DATA / "source_catalog.json")
    documents = catalog["documents"]
    ids = [doc["id"] for doc in documents]
    assert len(ids) == len(set(ids))

    for doc in documents:
        parsed = urlparse(doc["official_url"])
        assert parsed.scheme == "https"
        assert parsed.hostname and parsed.hostname.endswith("hust.edu.vn")
        assert "fbclid=" not in doc["official_url"]

        if doc["local_path"] is None:
            assert doc["pages"] is None
            assert doc["sha256"] is None
            continue

        path = ROOT / doc["local_path"]
        assert path.is_file(), doc["id"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == doc["sha256"]
        pdf = pymupdf.open(path)
        assert len(pdf) == doc["pages"], doc["id"]
        text_chars = sum(len(page.get_text()) for page in pdf)
        assert text_chars == doc["text_chars"], doc["id"]
        if doc["indexable"]:
            assert text_chars >= 10_000, doc["id"]


def test_manifest_keeps_the_existing_runtime_primary_source_first():
    catalog = _json(DATA / "source_catalog.json")
    primary = next(doc for doc in catalog["documents"] if doc["id"] == catalog["runtime_ingestion"]["source_id"])
    manifest = (DATA / "sources.md").read_text(encoding="utf-8")
    first_path = re.search(r"File tương ứng:\s*(.+)", manifest)
    first_url = re.search(r"URL chính thức:\s*(https://\S+)", manifest)
    assert first_path and first_url
    assert first_path.group(1).strip() == primary["local_path"].removeprefix("data/")
    assert first_url.group(1) == primary["official_url"]


def test_normalized_facts_are_grounded_in_the_cited_document_page():
    catalog = _json(DATA / "source_catalog.json")
    documents = {doc["id"]: doc for doc in catalog["documents"]}
    facts = _json(DATA / "normalized" / "admissions_facts_2026.json")["facts"]
    fact_ids = [fact["id"] for fact in facts]
    assert len(fact_ids) == len(set(fact_ids))

    cutoff_summary = _json(DATA / "normalized" / "cutoffs_2026_summary.json")
    online_evidence = {cutoff_summary["overall"]["evidence"]}
    online_evidence.update(item["evidence"] for item in cutoff_summary["program_scores"])

    for fact in facts:
        doc = documents[fact["source_id"]]
        evidence = fact["evidence"]
        assert evidence.strip()
        if doc["type"] == "pdf":
            assert doc["indexable"], fact["id"]
            assert 1 <= fact["page"] <= doc["pages"], fact["id"]
            pdf = pymupdf.open(ROOT / doc["local_path"])
            page_text = pdf[fact["page"] - 1].get_text()
            assert _normalized(evidence) in _normalized(page_text), fact["id"]
        else:
            assert fact["page"] is None, fact["id"]
            assert evidence in online_evidence, fact["id"]


def test_golden_cases_reference_known_facts_or_explicit_abstention_reasons():
    catalog = _json(DATA / "source_catalog.json")
    documents = {doc["id"]: doc for doc in catalog["documents"]}
    facts = _json(DATA / "normalized" / "admissions_facts_2026.json")["facts"]
    fact_by_id = {fact["id"]: fact for fact in facts}
    cases = [
        json.loads(line)
        for line in (DATA / "evaluation" / "admissions_2026_golden.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    case_ids = [case["id"] for case in cases]
    assert len(cases) >= 15
    assert len(case_ids) == len(set(case_ids))

    for case in cases:
        assert case["question"].strip()
        assert case["expected_answer"].strip()
        assert case["source_ids"]
        assert set(case["source_ids"]).issubset(documents)
        assert set(case["fact_ids"]).issubset(fact_by_id)

        if case["expected_behavior"].startswith("abstain_"):
            assert not case["fact_ids"]
            assert case.get("reason", "").strip()
        else:
            assert case["fact_ids"]
            cited_sources = {fact_by_id[fact_id]["source_id"] for fact_id in case["fact_ids"]}
            assert cited_sources.issubset(set(case["source_ids"]))


def test_unreadable_tsa_scan_is_never_treated_as_searchable_evidence():
    catalog = _json(DATA / "source_catalog.json")
    docs = {doc["id"]: doc for doc in catalog["documents"]}
    tsa = docs["hust-tsa-regulation-scan"]
    assert tsa["indexable"] is False
    assert tsa["status"] == "manual_ocr_required"

    facts = _json(DATA / "normalized" / "admissions_facts_2026.json")["facts"]
    assert all(fact["source_id"] != tsa["id"] for fact in facts)

    cases = [
        json.loads(line)
        for line in (DATA / "evaluation" / "admissions_2026_golden.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    tsa_cases = [case for case in cases if tsa["id"] in case["source_ids"]]
    assert tsa_cases
    assert all(case["expected_behavior"] == "abstain_source_not_searchable" for case in tsa_cases)
