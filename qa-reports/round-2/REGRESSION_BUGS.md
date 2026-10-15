# Báo cáo hồi quy vòng 2

## Không có lỗi hồi quy production mới được xác nhận

Các luồng đã xem ở production hoạt động nhất quán trong mẫu kiểm tra. Hai lỗi vòng 1 về quota dài và trùng lịch sử chỉ được xác minh một phần; xem [ROUND1_FIX_VERIFICATION.md](ROUND1_FIX_VERIFICATION.md). Không được coi các mục này là đã đóng hoàn toàn.

## Lỗi xác nhận trong bộ kiểm tra cục bộ

### TEST-001 — full test suite còn một test đỏ

- Lệnh: `pytest -q`
- Kết quả: **94 passed, 1 failed**.
- Test: `tests/test_api/test_mvp.py::test_llm_quote_validation_and_failure`.
- Quan sát: test kỳ vọng câu hỏi quota đi qua LLM và kiểm tra việc từ chối trích dẫn xấu; router hiện trả lời quota bằng đường trích xuất xác định trước nên mock LLM không được gọi theo kỳ vọng đó.
- Tác động: không có bằng chứng test này tương ứng lỗi trả lời production; nhưng suite không xanh và hợp đồng test/router cần được chủ động xác nhận.
- Cần làm: xác định route quota deterministic có chủ ý hay không; sau đó cập nhật test để kiểm tra nhánh đúng, giữ lại kiểm thử validation cho nhánh LLM.

Đây là lỗi test/độ lệch hợp đồng trong môi trường cục bộ, **không được ghi nhận là lỗi người dùng production**.

## Các lỗi lint còn tồn tại

`ruff check src tests` báo 3 lỗi: `F401`, `F841` trong `src/services/knowledge.py` và `I001` trong `tests/test_data/test_admissions_source_data.py`. Báo cáo vòng 1 cũng đã ghi nhận cùng các mã lỗi; audit này không sửa source.
