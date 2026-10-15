"""Read-only snapshot validation; --seal finalizes checksums, --package exports ZIP."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PIPELINE = ("normalize_admissions_data.py", "validate_admissions_data.py",
            "setup_data_ocr.py", "build_retrieval_dev.py")


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    content = path.read_bytes()
    # Git may convert CRLF on Windows. Public text uses canonical LF hashing;
    # PDF hashes always cover the exact original binary bytes.
    if path.suffix.lower() != ".pdf":
        content = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def snapshot_files():
    """Allowlist public artifacts; exclude databases, tools, caches and ZIPs."""
    paths = [DATA / name for name in ("README-data.md", "sources.md", "source_catalog.json")]
    for folder, suffixes in {
        "manifests": {".json"}, "normalized": {".jsonl", ".json", ".md"},
        "schemas": {".json"}, "extracted": {".txt", ".json", ".jsonl"},
        "quality": {".json", ".jsonl", ".md"}, "evaluation": {".jsonl"}, "eval": {".jsonl"},
    }.items():
        paths.extend(p for p in (DATA / folder).rglob("*") if p.is_file() and p.suffix in suffixes)
    paths.extend(DATA / s["local_path"] for s in read_json(DATA / "manifests/sources.json")["sources"])
    paths.append(DATA / "processed/chunks.jsonl")
    return sorted(set(paths))


def validate_content():
    manifest = read_json(DATA / "manifests/sources.json")
    source_list = manifest["sources"]
    sources = {s["source_id"]: s for s in source_list}
    assert len(sources) == len(source_list) == 6, "Duplicate/missing sources"
    assert len({s["sha256"] for s in source_list}) == 6, "Duplicate PDFs"
    catalog = {s["id"]: s for s in read_json(DATA / "source_catalog.json")["documents"]}
    assert len(catalog) == len(read_json(DATA / "source_catalog.json")["documents"])
    assert {s["runtime_source_id"] for s in source_list} == {key for key, doc in catalog.items() if doc["type"] == "pdf"}
    assert {s["runtime_source_id"] for s in manifest["external_sources"]} == {key for key, doc in catalog.items() if doc["type"] == "html"}
    records, chunks = rows(DATA / "normalized/records.jsonl"), rows(DATA / "processed/chunks.jsonl")
    record_map = {r["record_id"]: r for r in records}
    assert len(record_map) == len(records), "Duplicate record ID"
    assert len({c["chunk_id"] for c in chunks}) == len(chunks), "Duplicate chunk ID"
    tables = {}
    for source in sources.values():
        doc = catalog[source["runtime_source_id"]]
        assert source["local_path"] == doc["local_path"].removeprefix("data/")
        assert sha(DATA / source["local_path"]) == source["sha256"] == doc["sha256"]
        assert source["url"] == doc["official_url"] and source["page_count"] == doc["pages"]
        for table in rows(DATA / "extracted" / source["source_id"] / "tables.jsonl"):
            assert table["table_id"] not in tables
            assert table["source_version"] == source["sha256"]
            assert len(table["rows"]) == table["row_count"]
            assert all(len(row) == table["column_count"] for row in table["rows"])
            tables[table["table_id"]] = table
    for filename, items in [("record", records), ("chunk", chunks)]:
        validator = Draft202012Validator(read_json(DATA / "schemas" / f"{filename}.schema.json"))
        for item in items:
            validator.validate(item)
            source = sources[item["source_id"]]
            assert item["source_version"] == source["sha256"]
            assert 1 <= item["page_start"] <= item["page_end"] <= source["page_count"]
            assert item["evidence"]["local_path"] == source["local_path"]
            assert item["evidence"]["page_start"] == item["page_start"]
            assert item["evidence"]["page_end"] == item["page_end"]
            assert set(item.get("related_context_record_ids", [])).issubset(record_map)
            if item["review_status"] in {"needs_table_review", "needs_ocr_review"}:
                assert not item["answer_eligible"]
            location = item["evidence"].get("location") or {}
            refs = location.get("table_rows", []) + ([location] if "table_id" in location else [])
            for ref in refs:
                table = tables[ref["table_id"]]
                assert table["source_id"] == item["source_id"]
                assert item["page_start"] <= table["page"] <= item["page_end"]
                if "row_index" in ref:
                    assert 0 <= ref["row_index"] < table["row_count"]
                if "column_index" in ref:
                    assert 0 <= ref["column_index"] < table["column_count"]
    for chunk in chunks:
        parent = record_map[chunk["record_id"]]
        assert chunk["parent_id"] == parent["record_id"] and parent["record_type"] != "table"
        assert " ".join(chunk["text"].split()) in " ".join(parent["text"].split())
        for field in ("source_id", "source_version", "scope", "audience", "historical", "answer_eligible"):
            assert chunk[field] == parent[field], (chunk["chunk_id"], field)
        assert len(chunk["text"].split()) <= 450
        if chunk["extraction_method"] == "ocr":
            assert not chunk["answer_eligible"]
    for path in (DATA / "normalized").glob("*.jsonl"):
        for item in rows(path):
            assert item == record_map[item["record_id"]], f"View differs: {path}"
    programs = {r["program_code"]: r for r in records if r["record_type"] == "program"}
    assert len(programs) == 68
    assert programs["IT1"]["quota"] == 300 and programs["IT2"]["quota"] == 200
    assert programs["ITE10"]["quota"] == 120
    cutoffs = [r for r in records if r["record_type"] == "cutoff"]
    assert len(cutoffs) == 358
    assert all(r["historical"] and r["cutoff_year"] == r["admission_year"] in {2024, 2025}
               and 0 <= r["score"] <= r["scale"] for r in cutoffs)
    assert any(r.get("amount_vnd") == 700000 and r.get("unit") == "TCHP"
               and "Khoa học máy tính" in r["text"] for r in records)
    inventory = rows(DATA / "quality/page_inventory.jsonl")
    assert len(inventory) == 131
    for source in sources.values():
        pages = [p for p in inventory if p["source_id"] == source["source_id"]]
        assert len(pages) == source["page_count"]
        assert {p["page"] for p in pages} == set(range(1, source["page_count"] + 1))
        for entry in pages:
            prefix = DATA / "extracted" / source["source_id"] / f"page-{entry['page']:03d}"
            page = read_json(prefix.with_suffix(".json"))
            assert page["source_version"] == source["sha256"] and page["method"] == entry["method"]
            assert page["text"] == prefix.with_suffix(".txt").read_text(encoding="utf-8")
    assert all(p["text_characters"] > 0 for p in inventory)
    assert sum(p["method"] == "ocr" for p in inventory) == 20
    cases = rows(DATA / "eval/retrieval-dev.jsonl")
    assert len(cases) == len({c["case_id"] for c in cases}) == 25
    for case in cases:
        assert case["dataset_release"] == manifest["release"]
        assert case["corpus"] == "normalized_pdf_records_only"
        assert set(case["candidate_record_ids"]).issubset(record_map)
        if case["expected_source_id"]:
            assert case["candidate_record_ids"], case["case_id"]
            for ref in case["candidate_record_ids"]:
                record = record_map[ref]
                assert record["source_id"] == case["expected_source_id"]
                assert any(record["page_start"] <= page <= record["page_end"] for page in case["expected_pages"])
    release = read_json(DATA / "processed/release.json")
    assert release["release"] == manifest["release"]
    assert release["schema_version"] == 2
    for field, count in {"sources": len(sources), "pages": len(inventory), "tables": len(tables),
                         "records": len(records), "chunks": len(chunks), "programs": len(programs)}.items():
        assert release[field] == count, field
    return {"status": "passed", "records": len(records), "chunks": len(chunks), "cutoff_facts": len(cutoffs),
            "checks": ["JSON Schema", "unique IDs", "catalog/source SHA256 and paths", "page coverage",
                       "table provenance", "parent/context references", "view consistency", "68 programs",
                       "historical score year/scale", "TCHP units", "20 OCR pages", "development anchors",
                       "release counts", "complete snapshot and pipeline checksums"],
            "note": "Technical checks; not human accuracy certification."}


def main(seal=False, package=False):
    result = validate_content()
    release_path = DATA / "processed/release.json"
    release = read_json(release_path)
    if seal:
        release["checksum_format"] = "sha256_binary_pdf_utf8_lf_text"
        save(DATA / "quality/validation.json", result)
        release["files"] = {p.relative_to(DATA).as_posix(): sha(p) for p in snapshot_files()}
        release["pipeline_files"] = {"scripts/" + name: sha(ROOT / "scripts" / name) for name in PIPELINE}
        for name in ("requirements-data.txt", "requirements-data-validation.txt"):
            release["pipeline_files"][name] = sha(ROOT / name)
        save(release_path, release)
    assert release.get("checksum_format") == "sha256_binary_pdf_utf8_lf_text"
    expected = {p.relative_to(DATA).as_posix() for p in snapshot_files()}
    assert set(release["files"]) == expected, "Snapshot file list changed; rebuild and seal explicitly"
    for name, checksum in release["files"].items():
        assert sha(DATA / name) == checksum, f"Snapshot checksum mismatch: {name}"
    expected_pipeline = {"scripts/" + name for name in PIPELINE} | {"requirements-data.txt", "requirements-data-validation.txt"}
    assert set(release["pipeline_files"]) == expected_pipeline
    for name, checksum in release["pipeline_files"].items():
        assert sha(ROOT / name) == checksum, f"Pipeline checksum mismatch: {name}"
    if package:
        output = DATA / "releases" / f"{release['release']}.zip"
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(release["files"]):
                archive.write(DATA / name, "data/" + name)
            archive.write(release_path, "data/processed/release.json")
            for name in sorted(release["pipeline_files"]):
                archive.write(ROOT / name, name)
        print("Handoff ZIP:", output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seal", action="store_true", help="Finalize checksums after content validation")
    parser.add_argument("--package", action="store_true", help="Export the validated snapshot ZIP")
    args = parser.parse_args()
    main(args.seal, args.package)
