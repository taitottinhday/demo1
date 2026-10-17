# Báo cáo xử lý rủi ro AI/RAG — 17/10/2026

## Đã làm

- Sửa bộ chấm golden để cho phép nguồn chính thức tương đương đã khai báo, đồng thời vẫn bắt buộc mọi nguồn độc lập còn lại.
- Làm rõ câu hỏi benchmark học phí IT1 hỏi đơn giá mỗi TCHP trong năm học 2026–2027, không nhầm với tổng học phí năm.
- Ghi `generation_guard_reason` trong từng dòng eval để phân biệt nguyên nhân kiểm tra grounding/guardrail ở các lần chạy tiếp theo.
- Cập nhật tài liệu và metadata về trạng thái runtime: adapter records/chunks đã tích hợp; BM25 mặc định, hybrid là tùy chọn.
- Thêm test cho quy tắc nguồn tương đương và hướng dẫn việc còn cần cán bộ tuyển sinh xác minh trong [AI_RISK_REMEDIATION.md](../docs/AI_RISK_REMEDIATION.md).

## Kiểm tra

| Lệnh | Kết quả |
|---|---|
| `python -X utf8 scripts/validate_admissions_data.py --seal` | PASS — 1.132 records, 1.065 chunks, 358 facts; checksum snapshot được cập nhật. |
| `python -X utf8 scripts/validate_admissions_data.py` | PASS — xác thực lại snapshot ở chế độ chỉ đọc. |
| `python -m pytest tests/test_data/test_eval_source_expectations.py -q -p no:cacheprovider` | PASS — 2 tests. |
| `python -m ruff check scripts/evaluate_mvp.py tests/test_data/test_eval_source_expectations.py` | PASS. |
| Eval golden extractive | BLOCKED — tiến trình Windows bị kẹt khi tạo socketpair nội bộ của `asyncio`; đã dừng, không ghi nhận kết quả eval mới. |

## Còn cần xác minh

- Chưa chạy lại DeepSeek thật trong môi trường có credential; chưa xác nhận nguyên nhân 10 ca fallback trước đó đã được khắc phục.
- Chưa có holdout do con người chấm; điểm khớp nhãn tự động không phải độ chính xác đã chứng nhận.
- 19 trang TSA, bảng ngoại ngữ PDF trang 17, dữ liệu học bổng chi tiết và nội dung nghiệp vụ cần cán bộ đối chiếu nguồn gốc. Các mục OCR chưa được tự động nâng thành dữ liệu đủ điều kiện trả lời.

Không gửi email thật, không thay đổi dữ liệu production và không deploy. Báo cáo này không xác nhận chất lượng AI production.
