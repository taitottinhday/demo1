"""Validate the data contract, references, page coverage and important source facts."""

import hashlib
import json
import zipfile
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    sources = json.loads((DATA / "manifests/sources.json").read_text(encoding="utf-8"))["sources"]
    sources = {source["source_id"]: source for source in sources}
    records = rows(DATA / "normalized/records.jsonl")
    chunks = rows(DATA / "processed/chunks.jsonl")
    ids = {record["record_id"] for record in records}
    assert len(ids) == len(records), "Duplicate record ID"
    assert len({c["chunk_id"] for c in chunks}) == len(chunks), "Duplicate chunk ID"
    tables = {}
    for source in sources.values():
        assert hashlib.sha256((DATA / source["local_path"]).read_bytes()).hexdigest() == source["sha256"]
        for table in rows(DATA / "extracted" / source["source_id"] / "tables.jsonl"):
            tables[table["table_id"]] = table
    for filename, items in [("record", records), ("chunk", chunks)]:
        schema = json.loads((DATA / "schemas" / f"{filename}.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        for item in items:
            validator.validate(item)
            source = sources[item["source_id"]]
            assert item["source_version"] == source["sha256"]
            assert 1 <= item["page_start"] <= item["page_end"] <= source["page_count"]
            assert item["evidence"]["local_path"] == source["local_path"]
            location = item["evidence"].get("location") or {}
            for reference in location.get("table_rows", []) + ([location] if "table_id" in location else []):
                assert reference["table_id"] in tables
                if "row_index" in reference:
                    assert 0 <= reference["row_index"] < tables[reference["table_id"]]["row_count"]
    record_map = {record["record_id"]: record for record in records}
    for record in records:
        assert all(ref in ids for ref in record.get("related_context_record_ids", []))
    for chunk in chunks:
        assert chunk["record_id"] in ids
        assert chunk["parent_id"] == chunk["record_id"]
        parent = record_map[chunk["record_id"]]
        assert parent["record_type"] != "table"
        assert " ".join(chunk["text"].split()) in " ".join(parent["text"].split())
        if chunk["extraction_method"] == "ocr":
            assert not chunk["answer_eligible"], "OCR must be reviewed before answers"
    for path in (DATA / "normalized").glob("*.jsonl"):
        for item in rows(path):
            assert item == record_map[item["record_id"]], f"View differs: {path}"
    programs = {record["program_code"]: record for record in records if record["record_type"] == "program"}
    assert len(programs) == 68
    assert programs["IT1"]["quota"] == 300 and programs["IT2"]["quota"] == 200
    assert programs["ITE10"]["quota"] == 120
    cutoffs = [r for r in records if r["record_type"] == "cutoff"]
    assert cutoffs and all(
        r["historical"] and r["cutoff_year"] in {2024, 2025} and 0 <= r["score"] <= r["scale"] for r in cutoffs
    )
    assert any(
        r.get("amount_vnd") == 700000 and r.get("unit") == "TCHP" and "Khoa học máy tính" in r["text"] for r in records
    )
    assert any("12.4 Học bổng" in r["title"] and r["page_start"] == 25 and r["page_end"] == 26 for r in records)
    inventory = rows(DATA / "quality/page_inventory.jsonl")
    assert len(inventory) == 131
    for source in sources.values():
        pages = [page for page in inventory if page["source_id"] == source["source_id"]]
        assert {p["page"] for p in pages} == set(range(1, source["page_count"] + 1))
    assert all(p["text_characters"] > 0 for p in inventory), "A page still has no extracted text"
    assert sum(p["method"] == "ocr" for p in inventory) == 20
    release = json.loads((DATA / "processed/release.json").read_text(encoding="utf-8"))
    for name, checksum in release["files"].items():
        assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == checksum, name
    result = {
        "status": "passed",
        "checks": [
            "JSON Schema",
            "unique IDs",
            "source SHA256",
            "page coverage",
            "table provenance",
            "parent references",
            "view consistency",
            "68 programs",
            "historical score year/scale",
            "TCHP units",
            "20 OCR pages",
            "release checksums",
        ],
        "records": len(records),
        "chunks": len(chunks),
        "cutoff_facts": len(cutoffs),
        "note": "Technical checks; not human accuracy certification.",
    }
    (DATA / "quality/validation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for name in ("README-data.md", "eval/retrieval-dev.jsonl", "quality/validation.json"):
        release["files"][name] = hashlib.sha256((DATA / name).read_bytes()).hexdigest()
    release["pipeline_files"] = {
        "scripts/" + name: hashlib.sha256((ROOT / "scripts" / name).read_bytes()).hexdigest()
        for name in (
            "normalize_admissions_data.py",
            "validate_admissions_data.py",
            "setup_data_ocr.py",
            "build_retrieval_dev.py",
        )
    }
    (DATA / "processed/release.json").write_text(
        json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    output = DATA / "releases" / f"{release['release']}.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for folder in ("raw", "manifests", "extracted", "normalized", "quality", "schemas"):
            for path in sorted((DATA / folder).rglob("*")):
                if path.is_file() and path.suffix.lower() in {".pdf", ".json", ".jsonl", ".txt", ".md"}:
                    archive.write(path, "data/" + path.relative_to(DATA).as_posix())
        for name in ("processed/chunks.jsonl", "processed/release.json", "eval/retrieval-dev.jsonl"):
            archive.write(DATA / name, "data/" + name)
        archive.write(DATA / "README-data.md", "data/README-data.md")
        for name in (
            "normalize_admissions_data.py",
            "validate_admissions_data.py",
            "setup_data_ocr.py",
            "build_retrieval_dev.py",
        ):
            archive.write(ROOT / "scripts" / name, "scripts/" + name)
        archive.write(ROOT / "requirements-data.txt", "requirements-data.txt")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("Handoff ZIP:", output)


if __name__ == "__main__":
    main()
