# Báo cáo kiểm thử hồi quy chuyên sâu — 2026-10-15

## 1. Tóm tắt phạm vi, môi trường và giới hạn

Đã đọc hướng dẫn `README.md`, `README-MVP.md`, `.env.example`, `docker-compose.yml`, `Makefile`, tài liệu kiểm thử và các báo cáo QA có sẵn trong `qa-reports/round-2/`, cùng báo cáo QA ngày 10/10 và lượt rà soát ngày 15/10. Không tìm thấy `AGENTS.md` trong repository.

Trạng thái ban đầu: nhánh `main`, HEAD `936edbf`, `main...team/main [ahead 2]`; working tree có `M tests/conftest.py` và báo cáo `full-audit-2026-10-15.md` chưa track. `git diff` không hiện hunk cho `tests/conftest.py`; blob của file làm việc khớp blob ở index/HEAD, nhưng Git vẫn báo modified. Không sửa file đó. Báo cáo này là tệp mới.

Không có server local/test chạy khi bắt đầu. Để chạy các kiểm tra cục bộ, mã và bộ dữ liệu nguồn công khai được sao chép sang `E:\AI1\qa-regression-20261015-7b48b2`; bản sao không chứa `.env` hoặc `.git`, các DB/tài khoản tạm đã sao chép theo thư mục gốc được loại khỏi bản sao trước khi chạy test. Các fixture dùng thư mục `tmp_path`. Không chạy server hay kiểm thử ghi trên Railway. Không gửi email; không bật LLM hoặc gọi dịch vụ trả phí.

Kết quả: 22 test đồng bộ mục tiêu đạt; 13 test gợi ý ngành thất bại vì mock request không có `.cookies`; toàn bộ suite thu thập 105 test nhưng bị kẹt trong lần chạy đầu ở khởi tạo Windows Proactor event loop/socketpair. Ruff báo 3 lỗi hiện hữu; 8 file JavaScript và Python `src/tests` compile thành công. Có một lỗi trải nghiệm mức Thấp được xác nhận trước đó cùng ngày trên trang cán bộ production và được theo dõi lại ở báo cáo vòng trước. Không có lỗi nghiệp vụ production mới được xác nhận trong lượt hồi quy này.

## 2. Ma trận tính năng / vai trò

`PASS` chỉ áp dụng cho phạm vi con ghi trong ô; không hàm ý đã xác nhận toàn bộ luồng trên production.

| Nhóm / vai trò | Trạng thái | Bằng chứng / giới hạn |
|---|---|---|
| Sinh viên — tải landing, chương trình, FAQ, nguồn hiển thị, nhập câu hỏi | PASS một phần | Quan sát trực tiếp trước đó trong ngày; không gửi câu hỏi. Không xác minh phản hồi API mới trong lượt này. |
| Sinh viên — chatbot, hỏi thiếu dữ liệu/ngoài phạm vi, nhiều lượt, citation thực tế | BLOCKED | Không chạy được async suite hoặc backend local. Không gửi câu hỏi lên production. Bộ golden hiện có 20 ca chỉ được kiểm tra cấu trúc/dữ liệu chuẩn, chưa chạy qua câu trả lời hiện tại. |
| Sinh viên — so sánh chương trình / gợi ý ngành | BLOCKED một phần | UI so sánh có các lần mở trước; test API gợi ý ngành có 13 lỗi fixture trước business logic. Không kết luận lỗi sản phẩm từ các test này. |
| Sinh viên — đăng nhập, OTP, phiên hết hạn, lịch sử/phản hồi | BLOCKED một phần | Unit test session expiry mục tiêu PASS; các API đăng ký/OTP và luồng chủ ticket chưa chạy trong môi trường HTTP thực. |
| Sinh viên — chuyển cán bộ, consent, chống gửi lặp, xem ticket riêng | BLOCKED | Chưa chạy API async hoặc tạo ticket test; không thao tác dữ liệu production. |
| Cán bộ — danh sách, lọc “Tất cả”, chi tiết mẫu, nút làm mới | PASS một phần | Đã quan sát read-only trước đó trong ngày trên phiên demo; 3 ticket mẫu, refresh cập nhật timestamp. Không phản hồi/chuyển trạng thái. |
| Cán bộ — claim, phân công, trả lời, retry email, tìm kiếm/phân trang | BLOCKED | API/E2E async chưa chạy; không thao tác ghi. Test outbox đồng bộ riêng PASS nhưng không thay thế gửi email thật/mock qua toàn luồng. |
| Admin — đăng nhập/dashboard/KPI/tab/bộ lọc | BLOCKED | Chỉ quan sát màn đăng nhập trước đó; không dùng demo admin hay thông tin đăng nhập suy đoán. Test đơn vị demo-store isolation PASS. |
| Email — lưu phản hồi trước khi gửi, xác minh người nhận, lỗi provider | BLOCKED một phần | Các test đồng bộ về nội dung link an toàn và claim outbox/retry PASS. Không chạy test async gửi phản hồi/provider; không cấu hình SMTP/Resend, không gửi thư thật. |
| Dữ liệu nguồn — catalog, file PDF, checksum, page/fact, golden schema | PASS | 5 test `test_admissions_source_data.py` đạt; kiểm tra nguồn HTTPS, checksum/trang PDF, fact có bằng chứng đúng trang, catalog và behavior abstain cho TSA scan. |
| Cô lập demo và persistence | PASS một phần | Test demo store cô lập, session expiry, storage tách data source, persistence/replay và production config mục tiêu nằm trong 22 test đạt. Chưa chạy kiểm tra quyền HTTP đa tài khoản. |
| Bảo mật quyền/API | BLOCKED | Không chạy bypass/IDOR hoặc kiểm tra request trực tiếp. Test async role guard không chạy được; test đơn demo isolation xác nhận riêng dữ liệu sample không lộ sang store cơ sở. |

## 3. Ma trận viewport

| CSS viewport | Sinh viên | Cán bộ | Admin / account | Ghi chú |
|---:|---|---|---|---|
| 1440 px | PASS trực quan trước đó | PASS một phần (danh sách/mẫu) | BLOCKED dashboard | Chrome desktop qua CUA; không có browser version trong công cụ. |
| 1024 px | PASS trực quan trước đó | BLOCKED | BLOCKED | Không có lượt browser mới trong môi trường local. |
| 768 px | PASS gần mục tiêu (767/769) | BLOCKED | BLOCKED | Viewport override nhảy qua 768; không xác minh chính xác 768 CSS px. |
| 390 px | PASS trực quan trước đó | BLOCKED | BLOCKED | Không dùng điện thoại thật. |
| 360 px | PASS trực quan trước đó | BLOCKED | BLOCKED | Không dùng điện thoại thật. |

Ở các lần xem landing trước trong cùng ngày, không thấy tràn ngang, chồng nút hoặc hiện tượng trang buộc phóng to tại các viewport sinh viên đã nêu. Những kết quả đó là kiểm tra trực quan của giao diện production, không xác định được build production trùng với HEAD hiện tại. Chưa chạy được script `scripts/audit_frontend.py` trên local vì backend không khởi chạy trong event loop Windows hiện tại. Focus/keyboard, bàn phím ảo, xoay màn hình và trợ năng screen-reader chưa được xác minh lại trong đợt này.

## 4. Lỗi đã xác nhận

### BUG-001 — Hướng dẫn hàng chờ nói dữ liệu tự cập nhật nhưng chỉ cập nhật khi bấm nút

- **Mức độ:** Thấp
- **Trạng thái:** Đã xác nhận; đã ghi ở `full-audit-2026-10-15.md`, chưa có xác nhận đã sửa.
- **Nền tảng / viewport:** Chrome desktop qua CUA, khoảng 1440 CSS px, DPR 1.1; browser version không hiển thị.
- **Route:** `/staff`, danh sách ticket.
- **Tiền đề:** Phiên demo cán bộ; dữ liệu tải xong.
- **Tái hiện:** Mở trang; ghi dòng “Kết quả được cập nhật tự động mà không xóa từ khóa hiện tại.” và mốc cập nhật; chờ hơn 7 giây; so sánh timestamp; sau đó bấm “Làm mới”.
- **Thực tế:** Dòng hướng dẫn nói tự cập nhật nhưng timestamp không đổi trong khoảng chờ; nút “Làm mới” làm tải lại danh sách và đổi timestamp.
- **Mong đợi:** Hướng dẫn nêu rõ thao tác làm mới thủ công hoặc ứng dụng thực sự tự đồng bộ như câu chữ hiện tại.
- **Tần suất:** 1/1 lần quan sát đối chiếu trong phiên ngày 15/10; lỗi được giữ làm regression cần xác minh lại sau khi sửa.
- **Bằng chứng:** DOM/accessibility text và timestamp trước/sau chờ hơn 7 giây; sau bấm nút, timestamp mới xuất hiện. Chi tiết lần quan sát ở báo cáo QA cùng ngày.
- **Ảnh hưởng / hướng xử lý:** Cán bộ có thể chờ dữ liệu tự đến và bỏ lỡ ticket mới. Sửa nội dung trợ giúp hoặc khôi phục cập nhật nền theo yêu cầu sản phẩm.

## 5. Nghi vấn và vấn đề bộ kiểm thử

### TEST-001 — 13 test gợi ý ngành dùng request giả không có thuộc tính cookies

- **Trạng thái:** Lỗi harness đã xác nhận; chưa phải lỗi sản phẩm.
- **Bằng chứng:** Lệnh chọn 35 test đồng bộ trả `22 passed, 13 failed`. Cả 13 lỗi nằm trong `tests/test_api/test_program_guidance.py`; stack dừng ở `src/api/routes.py:335` khi `runtime()` đọc `request.cookies`. Fixture `guidance_runtime` dựng `SimpleNamespace` không có thuộc tính này. `Request` thật của Starlette có `cookies`, nên các ca này không đi tới logic gợi ý/nghiệm thu nghiệp vụ.
- **Cách phân loại:** Không gán FAIL cho chức năng người dùng cho tới khi chạy cùng một fixture Request hợp lệ hoặc API integration trên backend test.

### Lint

`python -m ruff check src tests` trả 3 lỗi: import `urlparse` không dùng và biến `page_fragment` không dùng ở `src/services/knowledge.py`; import chưa sắp xếp ở `tests/test_data/test_admissions_source_data.py`. Hai mục ở mã runtime là cảnh báo chất lượng/lint, chưa có bằng chứng gây lỗi chạy. Không sửa trong lượt QA.

## 6. Đánh giá AI/RAG

### Phương pháp và tiêu chí

- Bộ hiện tại `data/evaluation/admissions_2026_golden.jsonl` có **20 mẫu**: 5 `answer_with_source`, 13 `answer_with_scope`, 1 `abstain_source_not_searchable` và 1 `abstain_insufficient_source`.
- Các test dữ liệu kiểm tra mỗi ca có câu hỏi/đáp án chuẩn, nguồn tồn tại, fact ID hợp lệ; fact có trang PDF và bằng chứng khớp nội dung trang. TSA scan không được đánh dấu indexable và các ca liên quan yêu cầu abstain.
- Tiêu chí thực thi kỳ vọng: claim đúng/đủ phạm vi-năm-đối tượng/đơn vị; nguồn và trang hỗ trợ claim; abstain khi thiếu căn cứ. Tuy nhiên trong lượt này không chạy câu hỏi qua `Admissions.answer`, nên không có điểm đúng/sai câu trả lời hoặc citation thực tế.
- `scripts/evaluate_mvp.py` có một chế độ extractive và một chế độ LLM có thể gọi API trả phí; không chạy vì nó dùng async và chế độ LLM có rủi ro gọi provider thật. Không bật LLM.

### Kết quả và giới hạn

- **Chạy hiện tại:** 0/20 mẫu qua runtime; 20 mẫu chỉ được rà cấu trúc/ground truth qua test nguồn. Accuracy, citation precision/recall, groundedness, abstention quality, multi-turn consistency và latency: **chưa đo**.
- **Artifact cũ:** `eval/results/mvp-report.json` ghi lần đánh giá 04/10/2026 ở extractive mode, 40 ca (30 QA + 10 safety), auto label match 40/40, 27/30 trả lời QA và 10/10 safety. Đây là kết quả lịch sử, dựa trên so khớp từ khóa/trang tự động, không có human-reviewed accuracy, không phải holdout và không được coi là kết quả hồi quy hiện tại.
- Không gộp kết quả cũ với 20 mẫu hiện tại và không đưa ra phần trăm chất lượng AI cho bản đang kiểm thử.

## 7. Kết quả kiểm tra kỹ thuật

- `python -m pytest --collect-only -q`: **105 test collected**.
- Toàn suite: **BLOCKED/TIMEOUT**. `faulthandler_timeout=10` cho stack tại `asyncio.ProactorEventLoop` tạo `socketpair()` trong `pytest_asyncio` khi chuẩn bị test async đầu tiên `test_agent_basic_flow`. Lần chạy bị treo đã dừng; đây là blocker môi trường event loop, không phải kết quả pass/fail nghiệp vụ.
- Bộ kiểm tra đồng bộ chọn lọc: **22 passed** gồm kiểm tra corpus, public demo store isolation, schema gợi ý, các unit session/token/email/outbox/redaction/budget và persistence/config.
- Bộ chọn lọc có 13 test gợi ý ngành: **13 failed do fixture mock**, như TEST-001; cần sửa harness ở lượt khác rồi mới dùng kết quả để đánh giá sản phẩm.
- `python -m ruff check src tests`: **FAIL, 3 findings** như mục 5.
- `node --check`: **PASS 8/8 file JavaScript** trong `src/web`.
- `python -m compileall -q src tests`: **PASS**.
- Browser console/network/API latency: không có browser local nối vào backend; không thu log Network hay response code trong đợt này. Lần audit browser trước trong ngày không ghi nhận lỗi console ở trang cán bộ; điều đó không bao phủ mọi route/API.

## 8. Phần đã kiểm tra không phát hiện lỗi trong mẫu

- 5 test dữ liệu nguồn đảm bảo catalog có ID nguồn duy nhất, URL HTTPS, file/PDF/checksum/số trang khớp, fact trỏ tới bằng chứng đúng trang và TSA scan không bị xem như nguồn có thể tra cứu.
- Unit test demo public xác nhận ticket demo dùng store sample riêng, không trộn với record ở store cơ sở; không chứng minh toàn bộ bảo mật production.
- Unit test session expiry, OTP hết hạn, activation token một lần, email staff có hai liên kết hành động an toàn, redaction, giới hạn budget, notification outbox và replay idempotency mục tiêu đều nằm trong 22 test PASS.
- 8 file JavaScript không có lỗi cú pháp; Python source/tests compile thành công.
- Responsive landing quan sát trước đó không tái hiện lỗi viewport đã nêu trong ảnh; phạm vi chỉ là giao diện sinh viên và không xác minh mọi thiết bị.

## 9. An toàn dữ liệu và thao tác đã dừng

- Không sử dụng dữ liệu/ID cá nhân thật để dò quyền, không đăng ký tài khoản, không tạo ticket, không gửi phản hồi, không thay đổi trạng thái, không xóa dữ liệu.
- Không bấm nút demo admin; không thử đăng nhập bằng thông tin suy đoán.
- Không gửi email thật, không bật provider, không thực hiện thanh toán, không chạy migration, deploy, push hoặc commit.
- Các test đạt chỉ dùng fixture `tmp_path` trong bản sao test cô lập; không chạy trên database production. Không thao tác production trong lượt hồi quy này.
- Báo cáo QA trước đó ghi nhận trang sinh viên production có thể tự tạo phiên khách ẩn danh khi tải. Lượt này không mở lại trang production để tránh phát sinh side effect tương tự.

## 10. Ưu tiên trước khi phát hành

1. Xử lý BUG-001 và kiểm tra lại bằng staging có phiên cán bộ test.
2. Sửa fixture gợi ý ngành để dùng Starlette `Request` hoặc request giả có cookies, sau đó chạy lại các ca nghiệp vụ.
3. Chạy 105 test trên môi trường Python/Windows đã sửa event loop hoặc runner Linux/CI; ghi rõ kết quả full suite.
4. Chạy `ruff` và xử lý ba findings.
5. Chạy E2E staging bằng tài khoản sinh viên/cán bộ/admin tách biệt, DB disposable và mail catcher; kiểm tra ownership/role boundaries, retry, status sync và không trùng.
6. Chạy 20 golden case mới nhất qua extractive runtime, chấm thủ công claim + citation (tài liệu/trang/đoạn), thêm ca rewrite/multi-source/ambiguity/stale data; chỉ chạy LLM bằng mock hoặc key môi trường test riêng.
7. Chạy lại audit browser trên local/staging tại đủ 1440/1024/768/390/360 cho từng vai trò; bổ sung focus, tab order, keyboard/mobile thực nếu có.

**Đánh giá phát hành:** Chưa đủ bằng chứng để GO. Có lỗi hướng dẫn UI đã xác nhận, lint còn đỏ, full suite/API/browser hồi quy chưa hoàn tất và chưa đánh giá runtime AI/RAG hiện tại. Không có lỗi logic production mới được khẳng định từ kiểm tra này; các phần chưa chạy được giữ trạng thái BLOCKED, không suy diễn thành PASS.
