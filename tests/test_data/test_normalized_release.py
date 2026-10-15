"""Regression checks for the data/runtime boundary, without running OCR or AI."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from scripts import normalize_admissions_data as pipeline
from scripts.validate_admissions_data import sha

ROOT = Path(__file__).resolve().parents[2]


def test_text_checksums_survive_windows_checkout_but_pdf_hashes_are_binary(tmp_path):
    text = tmp_path / "source.json"
    text.write_bytes(b'{"a": 1}\n')
    expected = sha(text)
    text.write_bytes(b'{"a": 1}\r\n')
    assert sha(text) == expected
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"binary\r\n")
    assert sha(pdf) == hashlib.sha256(b"binary\r\n").hexdigest()


def test_pipeline_catalog_is_shared_with_runtime_and_ignores_unlisted_pdfs(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    payload = b"catalog-controlled-source"
    (raw / "english_k71_2026.pdf").write_bytes(payload)
    (raw / "unlisted.pdf").write_bytes(b"not an independent source")
    catalog = {"documents": [{"id": "runtime-english", "type": "pdf",
        "local_path": "data/raw/english_k71_2026.pdf", "official_url": "https://hust.edu.vn/source.pdf",
        "sha256": hashlib.sha256(payload).hexdigest()}]}
    (tmp_path / "source_catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    monkeypatch.setattr(pipeline, "DATA", tmp_path)
    sources, web = pipeline.sources()
    assert len(sources) == 1 and not web
    assert sources[0]["source_id"] == "hust-language-k71"
    assert sources[0]["runtime_source_id"] == "runtime-english"
    assert sources[0]["publication_date"] is None
    catalog["documents"][0]["sha256"] = "0" * 64
    (tmp_path / "source_catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        pipeline.sources()


def test_unreviewed_ocr_and_incomplete_tables_cannot_be_answer_eligible():
    data = ROOT / "data"
    records = [json.loads(line) for line in (data / "normalized/records.jsonl").read_text(encoding="utf-8").splitlines()]
    schema = json.loads((data / "schemas/record.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for status in ("needs_ocr_review", "needs_table_review"):
        original = next(r for r in records if r["review_status"] == status)
        validator.validate(original)
        with pytest.raises(ValidationError):
            validator.validate({**original, "answer_eligible": True})


def test_snapshot_validator_is_read_only_and_all_files_are_sealed():
    data = ROOT / "data"
    release_path = data / "processed/release.json"
    release = json.loads(release_path.read_text(encoding="utf-8"))
    paths = [data / name for name in release["files"]] + [release_path]
    before = {p: (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths}
    result = subprocess.run([sys.executable, "-X", "utf8", "scripts/validate_admissions_data.py"],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    after = {p: (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths}
    assert after == before


def test_release_has_no_duplicate_pdf_payloads():
    manifest = json.loads((ROOT / "data/manifests/sources.json").read_text(encoding="utf-8"))
    sources = manifest["sources"]
    assert len(sources) == len({s["sha256"] for s in sources}) == 6
    assert all(s["local_path"].startswith("raw/") and s["runtime_source_id"] for s in sources)
