# Kiểm thử hồi quy website — 17/10/2026

## 1. Tóm tắt

Kiểm thử `https://demo1-production-f54e.up.railway.app/` bằng duyệt giao diện live ở các trang demo cô lập và kiểm tra local/test. Không sửa mã nguồn, deploy, push hoặc commit; không gửi email, cũng không xác nhận thao tác ghi/xóa nghiệp vụ.

- **Lỗi đã xác nhận:** 1 lỗi responsive ở dashboard admin mobile: trang tràn ngang, tab cuối bị cắt.
- **Local:** 218 pytest passed; Ruff, compileall và `git diff --check` passed.
- **Trang sinh viên local:** không tràn ngang tại 1440, 1024, 768, 390, 360 px.
- **AI/RAG:** bộ golden 20 ca extractive khớp 15/20 nhãn nguồn/hành vi tự động. Năm ca lệch ID nguồn cần người rà lại; chưa xác nhận câu trả lời sai.
- **Khuyến nghị:** sửa lỗi admin mobile trước demo điện thoại, rà soát các nhãn golden và cập nhật test frontend có kỳ vọng lỗi thời.

## 2. Môi trường và cách kiểm thử

### Live

- Railway production: `demo1-production-f54e.up.railway.app`; duyệt bằng trình duyệt tích hợp. Kích thước viewport giả lập, không phải thiết bị mobile vật lý.
- Dùng demo cán bộ/admin sau khi xác nhận giao diện và cấu hình dự án dùng dữ liệu mẫu tách biệt, không gửi email.
- Viewport: 1440×900, 1024×768, 768×1024, 390×844, 360×800.
- Đọc `/health`, `/api/v1/status`, `/api/v1/demo/status`: health `ok`, production, nguồn sẵn sàng, demo bật. Corpus báo 68 chương trình, 796 passages index, 1.047 chunks; một nguồn scan TSA cần OCR thủ công.
- Lệnh PowerShell đọc API công khai bổ sung không phân giải được DNS trong phiên shell (`No such host is known`). Quan sát live bên trên dựa vào kết quả API từ trình duyệt.

### Local/test

- Repository `E:\AI1\P-051`, nhánh `main`, HEAD trước kiểm thử `90418ccaac531947d334fa4f4690de975dcc5141`.
- Cấu hình cô lập `APP_ENV=test`, `ANSWER_MODE=extractive`, dữ liệu tạm trong `.tmp-codex-qa-20261017`; không gọi nhà cung cấp AI.
- Pytest: **218 passed** (82,79 giây). Ruff, `compileall`, `git diff --check`: passed.
- Golden: 20 ca gồm 18 ca QA và 2 fallback an toàn; 15/20 khớp nhãn tự động. `accuracy_human=null`; không suy diễn độ chính xác thực tế từ bộ nhỏ này.
- Script responsive riêng ghi nhận không có lỗi JavaScript trang và không có HTTP response thất bại trong phiên local.

## 3. Ma trận kiểm thử

| Khu vực | Vai trò / môi trường | Viewport | Kết quả | Ghi chú |
|---|---|---:|---|---|
| Health, corpus, demo status | API live, chỉ đọc | Desktop | PASS | Nguồn sẵn sàng, demo enabled |
| Dashboard, lọc, tìm kiếm, ticket | Cán bộ demo live | 1440, 1024, 768, 390, 360 | PASS một phần | Ba ticket mẫu; không phản hồi hay đổi trạng thái |
| Dashboard admin, tổng quan và tab | Admin demo live | 1440, 1024, 768 | PASS | Overview, Ticket, Cán bộ, Đánh giá AI tải được |
| Dashboard admin responsive | Admin demo live | 390, 360 | FAIL | BUG-001 |
| Trang sinh viên/composer | Local/test | 1440, 1024, 768, 390, 360 | PASS | Không tràn ngang; không gửi câu hỏi |
| Đăng nhập/phân quyền tài khoản | Live | — | BLOCKED | Không có tài khoản test; không thử credential thật |
| Gửi ticket và xem phản hồi sinh viên | Production | — | BLOCKED | Không tạo dữ liệu; trang gốc có thể tạo phiên ẩn danh |
| Cán bộ phản hồi/email | Production | — | BLOCKED | Không ghi nghiệp vụ hoặc gửi email thật |
| AI/RAG production lượt này | Production | — | BLOCKED | Không gửi prompt mới đến production |
| PDF/trích dẫn trên thiết bị thật | Live | — | BLOCKED | Chưa kiểm tra thiết bị vật lý và toàn bộ luồng PDF |

## 4. Lỗi đã xác nhận

### BUG-001 — Dashboard admin tràn ngang, cắt tab cuối trên mobile

- **Mức độ:** Trung bình
- **Trạng thái:** Đã xác nhận
- **Nền tảng:** Railway live, trình duyệt tích hợp, viewport giả lập mobile
- **Route:** `/admin` → nút demo admin → dashboard
- **Tiền đề:** Mở dashboard admin demo.
- **Tái hiện:** Đặt viewport 360×800 hoặc 390×844 và quan sát hàng tab.
- **Thực tế:** document/body rộng 396 px ở cả hai viewport; tràn 36 px ở 360 và 6 px ở 390. Ở 360, tab “Đánh giá AI” bị cắt ở mép phải và xuất hiện cuộn ngang trang.
- **Mong đợi:** Trang không tràn ngang; mọi tab nhìn thấy và thao tác được, hoặc cuộn riêng hàng tab.
- **Tần suất:** Tái hiện ở cả 360 và 390 px; không thấy từ 768 px trở lên.
- **Bằng chứng:** Đo chiều rộng document/body và ảnh chụp trực quan trong phiên trình duyệt; ảnh không được xuất thành file.
- **Ảnh hưởng:** Admin mobile có thể không thấy/chọn được tab cuối.
- **Gợi ý:** Cho tab wrap hoặc cuộn ngang trong vùng riêng; giới hạn container và ngăn phần tử con làm nở toàn trang; xác minh điều hướng bàn phím.

## 5. Nghi vấn và kết quả cần rà soát

### RAG-001 — Năm ca golden lệch nhãn nguồn/hành vi

Đây là lệch giữa nhãn trong bộ đánh giá và ID nguồn trả về, **chưa xác nhận câu trả lời sai**:

- `HUST26-ADM-001`: kỳ vọng `hust-admission-regulation-2026`, kết quả `hust-admission-guide-2026` (trang 2, phương thức tuyển sinh).
- `HUST26-FEE-001`: kỳ vọng `hust-tuition-2026-2027`, kết quả `hust-admission-guide-2026` (trang 20, có nội dung học phí được hỏi).
- `HUST26-CUT-002`, `HUST26-CUT-003`, `HUST26-CUT-004`: kỳ vọng `hust-cutoffs-2026`, kết quả `hust-cutoffs-2026-table` (bảng điểm chuẩn chính thức).

**Đề xuất:** người phụ trách nội dung kiểm tra trích dẫn/trang rồi quyết định sửa nhãn chuẩn hay retrieval. Tỷ lệ 15/20 chỉ là khớp nhãn tự động trên bộ mẫu nhỏ, không phải điểm chính xác câu trả lời.

### QA-001 — Script audit frontend có kỳ vọng lỗi thời

`scripts.audit_frontend` dừng tại viewport đầu vì kỳ vọng `#follow-up .small-action` hiện khi trang còn trạng thái welcome. CSS hiện tại ẩn follow-up ở trạng thái này; gợi ý bắt đầu hội thoại nằm ở khu vực khác. Đây là sai lệch test harness, **không phải lỗi giao diện đã xác nhận**. Nên cập nhật test để kiểm tra đúng welcome/FAQ và chỉ kỳ vọng follow-up sau khi đã có hội thoại.

## 6. Dữ liệu, quyền và an toàn

- Không thử ID hoặc thông tin người dùng thật, không đổi role/quyền và không truy cập chéo dữ liệu thật.
- Trong dashboard demo chỉ xem ba ticket mẫu, lịch sử/AI response mẫu, một cán bộ mẫu và trạng thái rỗng của đánh giá AI. Bộ lọc `rejected` trả trạng thái không có ticket phù hợp.
- Không bấm trả lời, từ chối, đổi trạng thái, mời/tạo cán bộ, đặt lại mật khẩu hay xác nhận thao tác quản trị.
- Không gửi email; không gửi câu hỏi/tạo ticket mới trên Railway.
- Nút demo tạo phiên xác thực demo trong phạm vi dữ liệu demo cô lập; không có thao tác ghi nghiệp vụ hoặc gửi email.
- Không phát hiện console error/warning trong lần đọc log trình duyệt admin. Đây chỉ là quan sát của phiên đó.

## 7. Phần đã kiểm tra, chưa thấy lỗi

- Health và nguồn live sẵn sàng; trạng thái demo bật.
- Cán bộ demo hiển thị số liệu mẫu; danh sách và chi tiết ticket mở được. Tìm “học phí” trong trạng thái chờ trả 0 kết quả; chuyển sang tất cả tìm thấy ticket phù hợp. Làm mới cập nhật danh sách và giữ từ khóa.
- Admin demo tải tổng quan và các tab Ticket/Cán bộ/Đánh giá AI; lọc `rejected` đưa tới trạng thái rỗng phù hợp.
- Staff không tràn ngang tại năm viewport đo. Bộ lọc trên mobile cuộn ngang trong vùng riêng; scrollbar ẩn làm dấu hiệu cuộn chưa rõ, nhưng thao tác cuộn hoạt động.
- Trang sinh viên local/test không tràn ngang tại năm viewport; composer nằm trong khung nhìn.
- 218 kiểm thử tự động, lint, compile và whitespace đều đạt.

## 8. Giới hạn và thao tác dừng vì an toàn

- Không có tài khoản test được cấp để xác minh đăng nhập thường, phân quyền chéo vai trò, phiên hết hạn hoặc cô lập dữ liệu giữa hai sinh viên.
- Không chạy luồng ghi production: gửi câu hỏi, tạo ticket, phản hồi, đổi trạng thái, gửi email, quản trị cán bộ.
- Không đánh giá AI live lượt này; local extractive không xác minh cấu hình DeepSeek/Railway, chất lượng LLM live hoặc email.
- Không kiểm tra mobile vật lý, công cụ tương phản chuyên dụng, toàn bộ keyboard flow, toàn bộ PDF hoặc mọi tổ hợp truy vấn.
- Một nguồn scan TSA đang chờ OCR thủ công.
- Bộ test/golden nhỏ; nhãn nguồn cần người duyệt trước khi rút kết luận về chất lượng nội dung.

## 9. Kết luận phát hành

Chưa nên xem giao diện admin mobile là sẵn sàng demo: BUG-001 làm tab cuối bị cắt ở 360/390 px. Sửa và xác nhận lại trước demo qua điện thoại. Kết quả local đạt không thay thế staging an toàn cho luồng đăng nhập, gửi ticket, phản hồi và email. Rà soát năm ca nhãn RAG và cập nhật `scripts.audit_frontend` trước khi dựa vào chúng làm cổng hồi quy.

Không gửi email production; không tạo/sửa/xóa dữ liệu production; không deploy, push hoặc commit trong lượt này.
