import pytest

from src.config import Settings
from src.services.admissions import Admissions
from src.services.store import Store


def test_ingestion_indexes_every_readable_source_and_marks_unreadable_assets(knowledge):
    assert len(knowledge.documents) == 8
    assert knowledge.manifest["document_count"] == 8
    assert knowledge.manifest["indexable_pdf_count"] == 5
    assert "hust-tuition-2026-2027" in {chunk["source_id"] for chunk in knowledge.chunks}
    assert "hust-cutoffs-2026" in {chunk["source_id"] for chunk in knowledge.chunks}
    assert "hust-tsa-regulation-scan" in {item["id"] for item in knowledge.manifest["unavailable_sources"]}
    assert all(chunk["source_id"] != "hust-tsa-regulation-scan" for chunk in knowledge.chunks)
    assert all(chunk["source_id"] != "hust-scholarships-online" for chunk in knowledge.chunks)


@pytest.mark.asyncio
async def test_cutoff_answer_uses_exact_web_fact_and_does_not_overgeneralize(knowledge, tmp_path):
    service = Admissions(knowledge, Store(tmp_path / "cutoffs.db"), Settings(_env_file=None, answer_mode="extractive"))

    exact = await service.answer("Điểm chuẩn IT1 năm 2026 theo THPT bao nhiêu?")
    assert exact["kind"] == "answered"
    assert "29,27" in exact["response"]
    assert "TSA tương đương" in exact["response"]
    assert exact["sources"][0]["source_id"] == "hust-cutoffs-2026"
    assert exact["sources"][0]["page"] is None
    assert exact["sources"][0]["local_url"] is None
    assert exact["sources"][0]["url"].startswith("https://ts.hust.edu.vn/")

    missing = await service.answer("Điểm chuẩn IT2 năm 2026 là bao nhiêu?")
    assert missing["kind"] == "fallback"
    assert not missing["sources"]

    general = await service.answer("Điểm chuẩn chung HUST 2026 khoảng bao nhiêu?")
    assert "68 chương trình" in general["response"]
    assert "IT-E10" not in general["response"]


@pytest.mark.asyncio
async def test_tuition_uses_yearly_estimate_or_per_credit_source_as_asked(knowledge, tmp_path):
    service = Admissions(knowledge, Store(tmp_path / "tuition.db"), Settings(_env_file=None, answer_mode="extractive"))

    yearly = await service.answer("Học phí IT1 năm học 2026–2027 là bao nhiêu?")
    assert "28 - 40 triệu đồng/năm học" in yearly["response"]
    assert yearly["sources"][0]["source_id"] == "hust-admission-guide-2026"

    per_credit = await service.answer("Học phí IT1 theo TCHP bao nhiêu?")
    assert "700 nghìn đồng" in per_credit["response"]
    assert "TCHP" in per_credit["response"]
    assert per_credit["sources"][0]["source_id"] == "hust-tuition-2026-2027"
    assert per_credit["sources"][0]["page"] == 3
    assert "source_id=hust-tuition-2026-2027" in per_credit["sources"][0]["local_url"]

    postgraduate = await service.answer("Học phí thạc sĩ kỹ thuật năm học 2026–2027?")
    assert "790.000 đồng/TCHP" in postgraduate["response"]
    assert postgraduate["sources"][0]["source_id"] == "hust-tuition-2026-2027"
    assert postgraduate["sources"][0]["page"] == 6


@pytest.mark.asyncio
async def test_language_and_xttn_answers_keep_audience_and_year_scope(knowledge, tmp_path):
    service = Admissions(knowledge, Store(tmp_path / "scope.db"), Settings(_env_file=None, answer_mode="extractive"))

    english = await service.answer("Chuẩn tiếng Anh đầu ra chương trình chuẩn là gì?")
    assert "Bậc 3" in english["response"]
    assert english["sources"][0]["source_id"] == "hust-english-policy-k71"
    assert english["sources"][0]["page"] == 11

    talent = await service.answer("XTTN 1.3 cần điều kiện gì?")
    assert "8,00" in talent["response"]
    assert "Giáo dục thường xuyên" in talent["response"]
    assert talent["sources"][0]["source_id"] == "hust-talent-admission-2026"
    assert talent["sources"][0]["page"] == 7


@pytest.mark.asyncio
async def test_pdf_endpoint_serves_the_cited_document_and_rejects_unknown_ids(client):
    response = await client.get("/api/v1/source/pdf", params={"source_id": "hust-tuition-2026-2027"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")

    missing = await client.get("/api/v1/source/pdf", params={"source_id": "not-in-catalog"})
    assert missing.status_code == 404
