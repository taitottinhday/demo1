# Báo cáo E2E thí sinh → cán bộ → admin

## Phiên QA_TEST

Ticket production `TS-AC57CE06` đã tồn tại từ lần kiểm thử trước và được gắn ghi chú QA_TEST. Nội dung câu hỏi: “IT2 có chỉ tiêu bao nhiêu?”; câu trả lời AI có sẵn ghi quota **200** và nguồn “Thông tin tuyển sinh Đại học năm 2026”, PDF trang 10.

Sau khi người dùng xác nhận cụ thể thao tác E2E, cán bộ đã:

1. Đăng nhập vào luồng cán bộ bằng thông tin đăng nhập đã được người dùng hiệu chỉnh.
2. Nhận ticket QA_TEST đúng một lần; trạng thái đổi từ “Đang chờ” sang “Đang xử lý”.
3. Gửi đúng một phản hồi: “Theo tài liệu Thông tin tuyển sinh Đại học năm 2026, chỉ tiêu của mã IT2 (CNTT: Kỹ thuật Máy tính) là 200. Thí sinh vui lòng đối chiếu tài liệu tuyển sinh chính thức nếu có cập nhật mới.”
4. Ticket chuyển sang “Đã giải quyết”. Lịch sử có các sự kiện tạo ticket, nhận xử lý, gửi phản hồi và giải quyết.

Admin được đăng nhập lại; danh sách “Đã giải quyết” và chi tiết ticket xác nhận trạng thái, người phụ trách, câu hỏi, câu trả lời AI, nguồn trang 10 và phản hồi của cán bộ. Không chỉnh sửa/xóa dữ liệu nào khác.

## Kết quả

- Cán bộ: **PASS** — nhận một lần, gửi phản hồi một lần, giải quyết ticket.
- Admin: **PASS** — bản ghi cuối có trạng thái đã giải quyết và phản hồi, nguồn được giữ.
- Thí sinh: **PARTIAL** — các tab thí sinh đang mở đều thuộc session khác và hiện empty state “Chưa có yêu cầu”; không truy cập được session sở hữu ticket để chứng minh phản hồi hiển thị ở phía thí sinh. Không dùng mã ticket như thông tin xác thực và không dò endpoint để vượt ranh giới session.
- Toàn E2E: **PARTIAL** — hai vai trò nội bộ xác nhận kết quả; phía chủ ticket chưa xác minh.

## Bằng chứng

- [evidence/staff-queue.txt](evidence/staff-queue.txt): trạng thái cán bộ sau khi giải quyết và lịch sử.
- [evidence/admin-ticket.txt](evidence/admin-ticket.txt): chi tiết admin sau khi giải quyết.
- [evidence/README.md](evidence/README.md): cách xử lý ảnh/snapshot và giới hạn dữ liệu.

Ảnh chụp màn hình ticket đã được hiển thị trong cuộc hội thoại audit. Browser connector không xuất ảnh thành tệp local cho thư mục bằng chứng.
