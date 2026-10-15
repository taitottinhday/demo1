# Bàn giao data trước tích hợp AI — 15/10/2026

Nhánh làm việc: `feature/data-ai-integration`. Snapshot: `k71-2026-v2`.

## Kết quả

- Một catalog chung cho runtime và pipeline; 6 PDF chuẩn, 131 trang, 79 bảng, 20 trang OCR.
- 1.132 records, 1.065 chunks, 68 chương trình; 358 dữ kiện điểm chuẩn lịch sử 2024/2025.
- 864 records đủ điều kiện trích xuất kỹ thuật; 268 records bị chặn. Không có record được nâng thành staff-reviewed.
- Manifest có ánh xạ mã nguồn corpus/runtime, đường dẫn và SHA256. Bỏ 5 PDF trùng nội dung; không thay nội dung 6 PDF chuẩn.
- Schema v2, dẫn chứng bảng/hàng/cột, liên kết cha và ngữ cảnh, đơn vị TCHP, năm lịch sử và checksum toàn bộ snapshot/pipeline được kiểm tra.
- Lệnh validate mặc định chỉ đọc; `--seal` chốt checksum sau build, `--package` tạo ZIP công khai trong `data/releases/` (không commit ZIP).
- Checksum văn bản dùng LF chuẩn để Git checkout trên Windows/Linux không làm sai kết quả; PDF băm nguyên byte.

## Kiểm tra

Lệnh chỉ đọc: `python -X utf8 scripts/validate_admissions_data.py`.

Test data: `python -m pytest tests/test_data -q -p no:cacheprovider --basetemp=data/test-tmp/data-v2-check` — 10 test đạt.

Ruff: `python -m ruff check src tests scripts/normalize_admissions_data.py scripts/validate_admissions_data.py scripts/build_retrieval_dev.py` — đạt.

Toàn ứng dụng: 106 passed, 4 failed. Không sửa runtime hoặc các test ứng dụng trong đợt này:

| Test trong `tests/test_api/test_mvp.py` | Quan sát |
|---|---|
| `test_no_notification_before_reply_commit_or_to_unverified_student` | Gọi resolve khi chưa đăng nhập: API trả 401, test kỳ vọng 409. |
| `test_provider_failure_keeps_reply_and_retry_only_retries_email` | API retry trả `sending`; test kỳ vọng response đồng bộ là `sent`. |
| `test_demo_entry_points_work_in_test_and_are_disabled_in_production` | Fixture không có demo runtime; test kỳ vọng enabled. Test này còn kỳ vọng cấm demo production, khác luồng demo cô lập trong mã hiện tại. |
| `test_llm_quote_validation_and_failure` | Câu hỏi chỉ tiêu đi nhánh deterministic; test kỳ vọng nhánh LLM/mock. |

Đây là các bất đồng hợp đồng/fixture quan sát được, chưa kết luận mọi lỗi chỉ thuộc test. CI có bước validate data mới nhưng job toàn ứng dụng vẫn cần xử lý bốn mục này trước khi có thể báo xanh toàn bộ.

## Ranh giới tích hợp kế tiếp

Runtime vẫn dùng PDF + `admissions_facts_2026.json`; chưa dùng records/chunks. Không tạo embedding, vector index, reranker, gọi LLM hay gửi email thật trong đợt chuẩn hóa này.

OCR TSA và bảng ảnh trang 17 cần đối chiếu; ô gộp chưa rõ giữ null. Facts web năm 2026 được giữ riêng, chưa có bản lưu web đầy đủ. Bộ 25 ca development chỉ áp dụng cho corpus PDF chuẩn hóa; bộ golden 20 ca của runtime có facts web riêng. Không cộng hai bộ thành số đo accuracy.

Xem [README data](../data/README-data.md) để build lại và dùng hợp đồng dữ liệu v2. Bước tiếp theo là adapter records/chunks, bộ lọc phạm vi/năm/chất lượng và benchmark retrieval trước khi thay luồng AI.
