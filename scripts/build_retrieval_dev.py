"""Produce source-anchored development retrieval cases, never label them as holdout."""

import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
CASES = [
    ("IT1 có chỉ tiêu bao nhiêu năm 2026?", "admissions", [10], "programs", "answer"),
    ("IT2 xét tuyển bằng những phương thức nào?", "admissions", [10], "programs", "answer"),
    ("Học phí theo tín chỉ học phí của khoa học máy tính là bao nhiêu?", "tuition", [3], "tuition_rules", "answer"),
    ("Tín chỉ học tập và tín chỉ học phí có giống nhau không?", "tuition", [7], "tuition_rules", "answer"),
    ("Học phí học lại và học cải thiện được tính như thế nào?", "tuition", [5], "tuition_rules", "answer"),
    ("Trường có các loại học bổng nào?", "admissions", [25, 26], "scholarships", "answer"),
    ("Học bổng Trần Đại Nghĩa dành cho ai?", "admissions", [26], "scholarships", "answer"),
    ("Chương trình cử nhân và tích hợp kỹ sư kéo dài bao lâu?", "admissions", [24], "training_models", "answer"),
    ("Chương trình tài năng được tuyển chọn trước hay sau nhập học?", "admissions", [25], "training_models", "answer"),
    ("Chương trình liên kết quốc tế cấp bằng như thế nào?", "admissions", [25], "training_models", "answer"),
    ("Mã trường và địa chỉ liên hệ tuyển sinh là gì?", "admissions", [2], "contacts", "answer"),
    ("Liên hệ phòng tuyển sinh qua điện thoại nào?", "admissions", [2, 27], "contacts", "answer"),
    ("Nếu hai thí sinh bằng điểm thì dùng tiêu chí phụ gì?", "admissions", [16], "scoring_rules", "answer"),
    ("Đăng ký xét tuyển tài năng gồm những bước nào?", "regulations", [10], "application_steps", "answer"),
    ("Trúng tuyển rồi tôi phải xác nhận nhập học thế nào?", "regulations", [13], "enrollment_rules", "answer"),
    ("Trường hợp nào được bảo lưu kết quả trúng tuyển?", "regulations", [13], "enrollment_rules", "answer"),
    ("Ai được tham gia xét tuyển bổ sung?", "regulations", [13], "enrollment_rules", "answer"),
    ("Xét tuyển tài năng diện chứng chỉ quốc tế có điều kiện gì?", "talent", [5], "admission_rules", "answer"),
    ("Xét hồ sơ năng lực có phỏng vấn không?", "talent", [7, 10], "admission_rules", "answer"),
    ("Sinh viên K71 có thể xin miễn học ngoại ngữ khi nào?", "language", [4], "language_rules", "answer"),
    ("Quy định ngoại ngữ K71 bắt đầu áp dụng từ năm học nào?", "language", [5], "language_rules", "answer"),
    ("Bài thi TSA có những phần nào?", "tsa", [3], "exam_rules", "review_ocr_before_answer"),
    (
        "Bảng quy đổi chứng chỉ ngoại ngữ tuyển sinh quy định thế nào?",
        "admissions",
        [17],
        "language_rules",
        "review_ocr_before_answer",
    ),
    ("Điểm chuẩn 2026 của IT1 là bao nhiêu?", None, [], "cutoffs", "missing_2026_source"),
    ("Tôi có chắc chắn được học bổng 100% không?", None, [], "scholarships", "no_guarantee"),
]

records = [json.loads(line) for line in (DATA / "normalized/records.jsonl").read_text(encoding="utf-8").splitlines()]
cases = []
for i, (question, kind, pages, topic, behavior) in enumerate(CASES, 1):
    source_id = f"hust-{kind}-k71" if kind else None
    candidate_ids = [
        r["record_id"]
        for r in records
        if source_id == r["source_id"]
        and any(r["page_start"] <= p <= r["page_end"] for p in pages)
        and r["record_type"] != "table"
    ]
    cases.append(
        {
            "case_id": f"DEV-{i:03d}",
            "question": question,
            "topic": topic,
            "expected_source_id": source_id,
            "expected_pages": pages,
            "candidate_record_ids": candidate_ids,
            "expected_behavior": behavior,
            "label_status": "draft_page_anchors_need_relevance_review",
            "split": "development",
        }
    )
(DATA / "eval").mkdir(exist_ok=True)
(DATA / "eval/retrieval-dev.jsonl").write_text(
    "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases), encoding="utf-8"
)
print(f"Created {len(cases)} development cases; candidate IDs are page anchors, not graded relevance labels.")
