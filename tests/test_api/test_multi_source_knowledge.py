import pytest

from src.config import Settings
from src.services.admissions import Admissions
from src.services.knowledge import Knowledge
from src.services.store import Store


def test_hybrid_keeps_scope_filters_and_preserves_citations(knowledge):
    from unittest.mock import Mock

    k = Knowledge("data")
    k.__dict__.update(knowledge.__dict__)
    retrieval = Mock()

    def search(question, allowed, lexical, limit):
        candidates = {c["id"]: c for c in k.chunks if c["id"] in allowed}
        assert candidates
        assert all(c.get("audience") != "student" for c in candidates.values())
        assert all(c["kind"] not in {"fee", "program", "verified_fact", "overview"}
                   for c in candidates.values())
        return [dict(lexical[0][1], retrieval="hybrid", score=1)]

    retrieval.search.side_effect = search
    k.retrieval = retrieval
    result = k.search("Quy chế tuyển sinh xét tuyển đại học")
    assert result[0]["retrieval"] == "hybrid"
    assert k.citation(result[0])["source_id"]
    retrieval.search.assert_called_once()


def test_named_scholarship_does_not_retrieve_unrelated_tuition_or_awards(knowledge):
    from src.services.knowledge import normalize

    results = knowledge.search("Học bổng Trần Đại Nghĩa dành cho ai?")
    assert results
    assert all("tran dai nghia" in normalize(c["text"]) for c in results)


@pytest.mark.asyncio
async def test_public_scholarship_information_does_not_decide_personal_eligibility(knowledge, tmp_path):
    from src.services.knowledge import normalize

    service = Admissions(knowledge, Store(tmp_path / "scholarship.db"), Settings(_env_file=None))
    public = await service.answer("Học bổng Trần Đại Nghĩa dành cho ai?")
    assert public["kind"] == "answered"
    assert "kho khan" in normalize(public["response"])
    assert public["sources"][0]["source_id"] == knowledge.primary_source_id
    assert public["sources"][0]["end_page"] >= 26
    personal = await service.answer("Em có đủ điều kiện nhận học bổng Trần Đại Nghĩa không?")
    assert personal["kind"] == "fallback"
    assert not personal["sources"]


def test_hybrid_failure_falls_back_without_losing_bm25_evidence(knowledge):
    from unittest.mock import Mock

    k = Knowledge("data")
    k.__dict__.update(knowledge.__dict__)
    question = "Quy chế tuyển sinh xét tuyển đại học"
    expected = k.search(question)
    k.retrieval = Mock()
    k.retrieval.search.side_effect = TimeoutError("private connection details")
    assert k.search(question) == expected
    k.retrieval.search.assert_called_once()


@pytest.mark.asyncio
async def test_answer_cache_skips_retrieval(knowledge, tmp_path):
    from unittest.mock import Mock

    k = Knowledge("data")
    k.__dict__.update(knowledge.__dict__)
    service = Admissions(k, Store(tmp_path / "cache.db"), Settings(_env_file=None))
    first = await service.answer("Giới thiệu chương trình IT1")
    assert first["kind"] == "answered"
    k.search = Mock(side_effect=AssertionError("Cached answers must not run retrieval"))
    second = await service.answer("Giới thiệu chương trình IT1")
    assert second["cached"] is True
    assert second["response"] == first["response"]


def test_merged_passages_keep_evidence_and_do_not_merge_different_parents():
    base = {"source_id": "source", "page": 3, "end_page": 3,
            "title": "Article", "kind": "document_text", "record_id": "parent"}
    chunks = [
        {**base, "text": "First condition.", "evidence": "First condition."},
        {**base, "text": "Second exception.", "evidence": "Second exception."},
        {**base, "record_id": "another-parent", "text": "Unrelated rule.", "evidence": "Unrelated rule."},
    ]
    merged = Admissions._merge_source_chunks(chunks)
    assert len(merged) == 2
    assert merged[0]["text"] == merged[0]["evidence"] == "First condition. Second exception."
    assert merged[1]["text"] == "Unrelated rule."


@pytest.mark.asyncio
@pytest.mark.parametrize("question,needle,kind", [
    ("Quy chế TSA ghi hạn đăng ký thi 2026 vào ngày nào?", "chưa đủ căn cứ", "fallback"),
    ("Lệ phí thi TSA là bao nhiêu?", "chưa đủ căn cứ", "fallback"),
    ("Quy định ngoại ngữ mới áp dụng từ khi nào và cho khóa nào?", "2026", "answered"),
    ("Chương trình hợp tác TROY yêu cầu tiếng Anh đầu khóa tối thiểu thế nào?", "5.5", "answered"),
    ("700 nghìn đồng trong bảng là học phí một năm hay mỗi tín chỉ?", "TCHP", "answered"),
    ("Học kỳ hè có học phí như học kỳ chính không?", "1,5", "answered"),
    ("IT1 29,27 điểm có nghĩa là cần 29,27 điểm TSA không?", "THPT", "answered"),
])
async def test_policy_intents_do_not_invent_deadlines_or_inherit_program_context(knowledge, tmp_path, question, needle, kind):
    service = Admissions(knowledge, Store(tmp_path / "policies.db"), Settings(_env_file=None, answer_mode="extractive"))
    result = await service.answer(question, context="IT2")
    assert result["kind"] == kind
    assert needle.casefold() in result["response"].casefold()
    if kind == "fallback":
        assert result["sources"] == []
        assert "tsa.hust.edu.vn/dk" not in result["response"]


def test_ingestion_indexes_every_readable_source_and_marks_unreadable_assets(knowledge):
    assert len(knowledge.documents) == 8
    assert knowledge.manifest["document_count"] == 8
    assert knowledge.manifest["indexable_pdf_count"] == 5
    assert "hust-tuition-2026-2027" in {chunk["source_id"] for chunk in knowledge.chunks}
    assert "hust-cutoffs-2026" in {chunk["source_id"] for chunk in knowledge.chunks}
    assert "hust-tsa-regulation-scan" in {item["id"] for item in knowledge.manifest["unavailable_sources"]}
    assert all(chunk["source_id"] != "hust-tsa-regulation-scan" for chunk in knowledge.chunks)
    assert all(chunk["source_id"] != "hust-scholarships-online" for chunk in knowledge.chunks)


def test_supplemental_passages_use_normalized_quality_and_parent_references(knowledge):
    assert knowledge.manifest["data_release"] == "k71-2026-v2"
    passages = [c for c in knowledge.chunks if c["kind"] == "document_text"]
    assert len(passages) == knowledge.manifest["normalized_passages"] > 0
    for passage in passages:
        parent = knowledge.records[passage["record_id"]]
        assert parent["answer_eligible"] is True
        assert parent["extraction_method"] == "native"
        assert parent["historical"] is False
        assert parent["scope"] == "undergraduate_regular"
        assert set(passage["related_context_record_ids"]).issubset(knowledge.records)
        assert knowledge.citation(passage)["source_id"] in knowledge.documents_by_id


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
