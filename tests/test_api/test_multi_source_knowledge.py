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


@pytest.mark.asyncio
@pytest.mark.parametrize("question", [
    "điều kiện học bổng của trường",
    "Em muốn hỏi điều kiện học bổng của trường",
    "Học bổng khuyến khích học tập có các mức nào?",
])
async def test_scholarship_policy_uses_complete_pdf_section_without_api(knowledge, tmp_path, question):
    from unittest.mock import AsyncMock

    service = Admissions(knowledge, Store(tmp_path / "policy.db"),
                         Settings(_env_file=None, answer_mode="llm"))
    service.generate = AsyncMock(side_effect=AssertionError("Policy quotes need no paid API"))
    result = await service.answer(question, context="IT1")
    assert result["kind"] == "answered"
    assert result["mode"] == "extractive"
    assert "loại xuất sắc" in result["response"]
    assert "1,5" in result["response"]
    assert len(result["sources"]) == 1
    assert result["sources"][0]["page"] == 25
    assert result["sources"][0]["end_page"] == 26
    assert "12.6" not in result["response"]
    service.generate.assert_not_called()


@pytest.mark.asyncio
async def test_historical_cutoff_is_not_replaced_with_current_year(knowledge, tmp_path):
    service = Admissions(knowledge, Store(tmp_path / "historical.db"), Settings(_env_file=None))
    result = await service.answer("điểm chuẩn của năm 2025", context="IT1")
    assert result["kind"] == "answered"
    assert "năm 2025" in result["response"]
    assert all(s["year"] == 2025 for s in result["sources"])
    assert all(s["source_id"] == knowledge.primary_source_id for s in result["sources"])
    missing = await service.answer("Điểm chuẩn IT1 năm 2023?")
    assert missing["kind"] == "fallback"
    assert not missing["sources"]


@pytest.mark.asyncio
@pytest.mark.parametrize("question", [
    "Hạn nộp học bổng khuyến khích học tập là khi nào?",
    "Hồ sơ học bổng Trần Đại Nghĩa gồm giấy tờ gì?",
    "Em học khá thì có học bổng không?",
])
async def test_scholarship_policy_does_not_invent_awards_or_application_details(knowledge, tmp_path, question):
    service = Admissions(knowledge, Store(tmp_path / "limits.db"), Settings(_env_file=None))
    result = await service.answer(question)
    assert result["kind"] == "fallback"
    assert not result["sources"]


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
    assert len(knowledge.documents) == 9
    assert knowledge.manifest["document_count"] == 9
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
        assert parent["scope"] == "undergraduate_regular"
        assert set(passage["related_context_record_ids"]).issubset(knowledge.records)
        assert knowledge.citation(passage)["source_id"] in knowledge.documents_by_id


def test_every_eligible_in_scope_native_chunk_is_loaded(knowledge):
    import json
    from pathlib import Path

    expected = set()
    for line in Path("data/processed/chunks.jsonl").read_text(encoding="utf-8").splitlines():
        c = json.loads(line)
        parent = knowledge.records[c["record_id"]]
        if (c["answer_eligible"] and parent["answer_eligible"]
                and c["scope"] == "undergraduate_regular" and c["extraction_method"] == "native"):
            expected.add(c["chunk_id"])
    actual = {c["id"] for c in knowledge.chunks if c.get("record_id")}
    assert actual == expected
    assert knowledge.manifest["normalized_coverage"]["indexed_chunks"] == len(expected)


def test_historical_rows_require_exact_year_program_and_method(knowledge):
    rows = knowledge.search("Điểm chuẩn IT1 năm 2025 theo THPT?")
    assert rows
    assert all(c["admission_year"] == 2025 and c["method"] == "THPT"
               and "IT1" in c["program_codes"] for c in rows)
    assert not knowledge.search("Điểm chuẩn năm 2025?")
    assert not knowledge.search("Điểm chuẩn IT1 năm 2023?")
    assert all(not c.get("historical") for c in knowledge.search("Thông tin tuyển sinh IT1"))


@pytest.mark.asyncio
@pytest.mark.parametrize("question", [
    "Theo mô hình đào tạo, chương trình cử nhân kéo dài bao lâu và cấp bằng gì?",
    "Mô hình tích hợp Cử nhân–Thạc sĩ được mô tả thế nào về thời gian và bằng cấp?",
])
async def test_general_training_models_are_not_mistaken_for_program_or_postgraduate_requests(
    knowledge, tmp_path, question
):
    service = Admissions(knowledge, Store(tmp_path / "models.db"), Settings(_env_file=None))
    result = await service.answer(question)
    assert result["kind"] == "answered"
    assert result["sources"]
    assert all(s["source_id"] == knowledge.primary_source_id for s in result["sources"])


@pytest.mark.asyncio
async def test_cutoff_answer_uses_exact_web_fact_and_does_not_overgeneralize(knowledge, tmp_path):
    service = Admissions(knowledge, Store(tmp_path / "cutoffs.db"), Settings(_env_file=None, answer_mode="extractive"))

    exact = await service.answer("Điểm chuẩn IT1 năm 2026 theo THPT bao nhiêu?")
    assert exact["kind"] == "answered"
    assert "29,27" in exact["response"]
    assert "THPT: 29,27/30" in exact["response"]
    assert exact["sources"][0]["source_id"] == "hust-cutoffs-2026-table"
    assert exact["sources"][0]["page"] is None
    assert exact["sources"][0]["local_url"] is None
    assert exact["sources"][0]["url"].startswith("https://hust.edu.vn/")

    missing = await service.answer("Điểm chuẩn ZZ999 năm 2026 là bao nhiêu?")
    assert missing["kind"] == "fallback"
    assert not missing["sources"]

    general = await service.answer("Điểm chuẩn chung HUST 2026 khoảng bao nhiêu?")
    assert "68 chương trình" in general["response"]
    assert "IT-E10" not in general["response"]


@pytest.mark.asyncio
@pytest.mark.parametrize("question", [
    "Điểm chuẩn ZZ999 năm 2026 theo TSA?",
    "Điểm chuẩn ZZ999 năm 2026 XTTN diện 1.2?",
    "Điểm chuẩn EE2 năm 2025 XTTN diện 1.3?",
])
async def test_cutoff_never_substitutes_another_method_or_unspecified_xttn(knowledge, tmp_path, question):
    service = Admissions(knowledge, Store(tmp_path / "cutoff-method.db"), Settings(_env_file=None))
    answer = await service.answer(question)
    assert answer["kind"] == "fallback"
    assert not answer["sources"]
    assert "29,27" not in answer["response"]
    assert "85.44" not in answer["response"]


@pytest.mark.asyncio
async def test_cutoff_summary_does_not_repeat_score_or_hide_xttn_scope(knowledge, tmp_path):
    service = Admissions(knowledge, Store(tmp_path / "cutoff-render.db"), Settings(_env_file=None))
    current = await service.answer("Điểm chuẩn IT1 2026?")
    assert current["response"].count("29,27") == 1
    historical = await service.answer("Điểm chuẩn EE2 2025?")
    assert "không tách diện 1.2 và 1.3" in historical["response"]
    assert historical["response"].count("không áp dụng thay") == 1
    ee2 = await service.answer("điểm chuẩn EE2 2026")
    assert ee2["kind"] == "answered"
    assert ee2["response"].count("28,98") == 1
    assert ee2["sources"][0]["source_id"] == "hust-cutoffs-2026-table"
    for year, score in [(2025, "28,48"), (2024, "28,16")]:
        past = await service.answer(f"điểm chuẩn EE2 {year}")
        assert score in past["answer_sections"]["short_answer"]


def test_every_captured_2026_program_score_has_runtime_fact(knowledge):
    import json
    from pathlib import Path

    summary = json.loads(Path("data/normalized/cutoffs_2026_summary.json").read_text(encoding="utf-8"))
    facts = [c for c in knowledge.chunks if c.get("topic") == "cutoff"]
    for program in summary["program_scores"]:
        assert any(program["evidence"] == c["evidence"]
                   and program["program_code"] in c["text"] for c in facts)


@pytest.mark.asyncio
async def test_automation_alias_and_complete_method_table(knowledge, tmp_path):
    service = Admissions(knowledge, Store(tmp_path / "automation.db"), Settings(_env_file=None))
    for question in ["điểm chuẩn tự động hóa 2026", "diem chuan tu dong hoa 2026", "điểm chuẩn EE2 2026"]:
        answer = await service.answer(question)
        assert answer["kind"] == "answered"
        assert all(score in answer["response"] for score in ["28,98/30", "89,50/100", "90,35/100", "76,50/100"])
        assert len(answer["sources"]) == 1
    for method, score in [("TSA", "76,50"), ("XTTN 1.2", "89,50"), ("XTTN 1.3", "90,35")]:
        answer = await service.answer(f"điểm chuẩn tự động hóa 2026 theo {method}")
        assert score in answer["response"]
        assert "THPT: 28,98" not in answer["response"]
    advanced = knowledge.program_matches("điểm chuẩn tự động hóa tiên tiến 2026")
    assert [p["code"] for p in advanced] == ["EEE8"]
    explicit = knowledge.program_matches("điểm chuẩn tự động hóa EE1 2026")
    assert [p["code"] for p in explicit] == ["EE1"]
    table = [c for c in knowledge.chunks if c.get("cutoff_methods")]
    assert len(table) == len({c["program_code"] for c in table}) == 68
    for row in table:
        retrieved = knowledge.search(f"Điểm chuẩn {row['program_code']} năm 2026")
        assert retrieved[0]["program_code"] == row["program_code"]
        assert retrieved[0]["cutoff_methods"] == row["cutoff_methods"]


@pytest.mark.asyncio
async def test_chat_followups_work_in_llm_mode_without_provider_for_source_policies(knowledge, tmp_path):
    from unittest.mock import AsyncMock

    service = Admissions(knowledge, Store(tmp_path / "followups.db"), Settings(_env_file=None, answer_mode="llm"))
    service.generate = AsyncMock(side_effect=AssertionError("These source policies must work without LLM synthesis"))
    cases = [
        ("điểm chuẩn tự động hóa 2026", "28,98"),
        ("Học phí EE2 năm học 2026–2027 là bao nhiêu?", "28 - 40"),
        ("Điều kiện ngoại ngữ EE2 là gì?", "không nêu ngưỡng chứng chỉ riêng"),
        ("Đăng ký xét tuyển đánh giá tư duy như thế nào?", "https://tsa.hust.edu.vn/dk"),
        ("Điều kiện học bổng của trường là gì?", "1,5"),
    ]
    for question, expected in cases:
        result = await service.answer(question, context="EE2")
        assert result["kind"] == "answered", (question, result)
        assert expected in result["response"]
        assert result["sources"] and result["tokens"] == 0
        if "học bổng" in question:
            assert len(result["response"]) < 1500
    service.generate.assert_not_called()


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


@pytest.mark.asyncio
async def test_public_document_catalog_lists_every_source_without_internal_paths(client, knowledge):
    result = await client.get("/api/v1/sources")
    assert result.status_code == 200
    catalog = result.json()
    assert catalog["count"] == 9
    assert {s["id"] for s in catalog["documents"]} == {s["id"] for s in knowledge.documents}
    for document in catalog["documents"]:
        assert "local_path" not in document and "resolved_path" not in document
        assert document["status_label"] and document["scope"]
        if document["type"] == "pdf":
            response = await client.get(document["local_url"])
            assert response.status_code == 200
            assert response.content.startswith(b"%PDF-")
        else:
            assert document["local_url"] is None
    scan = next(s for s in catalog["documents"] if s["id"] == "hust-tsa-regulation-scan")
    assert "chưa dùng" in scan["status_label"]
