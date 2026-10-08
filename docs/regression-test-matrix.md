# Regression test matrix — P-051

Ngày chạy: 2026-10-08
Phạm vi: backend API, frontend public/account/staff/admin và các nâng cấp responsive/accessibility.
Môi trường: Windows, Python 3.11, Node.js v22.14.0, Chrome headless; chạy trên dữ liệu local. Không dùng tài khoản hoặc dữ liệu production.

## Quy ước

| Trạng thái | Ý nghĩa |
| --- | --- |
| PASS | Đã chạy và đạt |
| FAIL | Đã chạy nhưng có assertion/lỗi cần sửa |
| BLOCKED | Đã chạy nhưng bị chặn bởi môi trường hoặc điều kiện ngoài test |
| NOT VERIFIED | Chưa thể kết luận, thường do thiếu tài khoản/dữ liệu production |

## Backend

| Nhóm | Bài kiểm tra | Test/command | Kết quả |
| --- | --- | --- | --- |
| Static quality | Ruff toàn repository | `python -m ruff check .` | PASS |
| Compile | Biên dịch Python | `python -m compileall -q src tests scripts` | PASS |
| Scope chatbot | general/program/ambiguous, ưu tiên mã chương trình trong câu hỏi | `test_chat_scope_prioritizes_explicit_program_and_handles_general_questions` | Có test; chưa chạy được do pytest async bị treo |
| Handover isolation | Candidate không xem ticket của session khác; staff/admin phân quyền | `test_handover_isolation_consent_idempotency_and_staff`, `test_staff_queue_is_scoped_to_owner_but_keeps_shared_waiting_queue` | Có test; chưa chạy được do pytest async bị treo |
| Claim cạnh tranh | Hai cán bộ claim cùng ticket chỉ một người thắng | `test_staff_claim_is_atomic_and_only_owner_can_resolve` | Có test; chưa chạy được do pytest async bị treo |
| Compare API | Dữ liệu thiếu, mã sai, chọn trùng | `test_comparison_is_grounded_and_validated`, `test_comparison_reports_invalid_selection_in_vietnamese` | Có test; chưa chạy được do pytest async bị treo |
| Handover idempotency | Cùng `request_key` không tạo ticket trùng | `test_handover_isolation_consent_idempotency_and_staff` | Có test; chưa chạy được do pytest async bị treo |
| KPI | numerator/denominator/formula/timezone | `test_handover_audit_events_and_metrics_formula`, `test_metrics_with_sample_data` | Có test; chưa chạy được do pytest async bị treo |
| OTP | Che email, expiry, resend, dùng lại mã | `test_otp_metadata_resend_and_reuse`, `test_expired_otp_is_rejected` | Test đồng bộ liên quan PASS; test async chưa chạy được |
| Activation token | Hash, hết hạn, dùng một lần | `test_staff_invite_token_is_hashed_expiring_and_one_time` | PASS |
| Lock/unlock staff | Trả ticket về waiting, audit lock/unlock | `test_lock_officer_releases_tickets` | Có test; chưa chạy được do pytest async bị treo |
| Password reset | Không trả plaintext/password hash, audit reset | `test_admin_can_reset_officer_password_without_exposing_it` | Có test; chưa chạy được do pytest async bị treo |
| Redaction | Email, CCCD, điện thoại, mật khẩu không lộ | `test_redaction`, `test_staff_metrics_and_payload_redaction_match_real_ticket_state` | `test_redaction` PASS; test async chưa chạy được |
| Sync subset | Các test không cần pytest-asyncio | `pytest -q -k "staff_invite_token_is_hashed_expiring_and_one_time or expired_otp_is_rejected or student_staff_and_admin_sessions_expire or staff_email_has_two_safe_action_links or test_redaction or production_rejects_demo_credentials or budget_is_hard_limit"` | **7 passed, 51 deselected** |

### Full pytest

Đã chạy với hard timeout 45 giây và `faulthandler_timeout=15`:

```text
python -c "import subprocess,sys; result=subprocess.run([sys.executable,'-m','pytest','-q','-o','faulthandler_timeout=15'],timeout=45); raise SystemExit(result.returncode)"
```

Kết quả: **BLOCKED/TIMEOUT**. `pytest_asyncio` bị treo khi tạo event loop Windows tại `socketpair()` (`ProactorEventLoop`). Thử lại với `WindowsSelectorEventLoopPolicy` vẫn tái hiện tại `selector_events.py`. Đây là blocker của môi trường chạy test, chưa phải kết luận test nghiệp vụ fail.

Pytest collection vẫn thành công: **58 tests collected**.

## Frontend

| Nhóm | Bài kiểm tra | Test/command | Kết quả |
| --- | --- | --- | --- |
| JavaScript syntax | Toàn bộ file `.js` tracked | `node --check` cho 5 file JavaScript | PASS |
| Responsive | Applicant tại 1366×768, 1440×900, 1280×1024, 768×1024, 390×844 | `scripts/audit_frontend.py` | PASS |
| Accessibility | Label input, accessible name button, aria-live, không tràn ngang | `scripts/audit_frontend.py` | PASS |
| Keyboard/focus | Tab, Enter chọn chương trình, Escape đóng drawer, focus vào select compare lỗi đầu tiên | `scripts/audit_frontend.py` | PASS |
| Mobile layout | Drawer chương trình, chip câu hỏi, safe-area ô nhập | `scripts/audit_frontend.py` tại 390×844 | PASS |
| Desktop layout | Chat shell và lịch sử chat tại 1440×900 | `scripts/audit_frontend.py` | PASS |
| Compare | Thiếu lựa chọn, chọn trùng, reset kết quả | `scripts/audit_frontend.py` và `scripts/check_browser.py` | Audit mới PASS; smoke cũ bị chặn ở staff queue |
| Staff empty/search | Empty state, xóa từ khóa/bộ lọc | `scripts/check_browser.py` | NOT VERIFIED đầy đủ do smoke cũ dừng trước bước này |
| Admin empty state | Empty detail khi chưa chọn ticket | HTML/JS có trạng thái; chưa đăng nhập production | NOT VERIFIED production |
| Auto-refresh draft | Không ghi đè nội dung reply đang soạn | Có assertion trong `scripts/check_browser.py` | NOT VERIFIED đầy đủ do smoke cũ dừng trước bước này |

Lệnh audit frontend:

```text
python -m scripts.audit_frontend --url http://127.0.0.1:8000 --browser "C:/Program Files/Google/Chrome/Application/chrome.exe"
```

Kết quả: `Responsive/accessibility/keyboard audit passed for 5 applicant viewports and staff/admin checks.`

Smoke test chức năng cũ `scripts/check_browser.py` dừng ở assertion staff queue: test kỳ vọng 1 item nhưng store local có 18–19 ticket. Kiểm tra riêng bằng mã ticket vẫn lọc đúng 1 item. Cần cô lập/reset dữ liệu demo trước khi dùng smoke test này làm gate.

## Chưa thể kiểm chứng

- Chưa kiểm thử tài khoản, email, token và dữ liệu thực tế trên Railway/Vercel production.
- Chưa kiểm tra Gmail mobile/Chrome mobile bằng tài khoản thật trong đợt này.
- Chưa chạy được toàn bộ pytest async vì lỗi tạo event loop của môi trường Windows.
- Chưa kết luận SLA, SMTP/Resend delivery hoặc trạng thái domain production.

Đợt kiểm thử local ban đầu không push/deploy. Kết quả kiểm tra sau khi push lên nhánh triển khai được ghi ở phần dưới đây.

## Kiểm tra sau push

Phần này được cập nhật sau khi commit được push lên repository đích và Railway hoàn tất hoặc báo lỗi deployment. Các thao tác production có thể làm thay đổi dữ liệu (tạo ticket, claim, gửi email, khóa tài khoản) không được chạy nếu không có tài khoản/dữ liệu kiểm thử riêng.
