# Prompt v0 — Trợ lý tuyển sinh X, HUST 2026

Thiết kế lại trang chủ web cho Trợ lý tuyển sinh X của Đại học Bách khoa Hà Nội, năm 2026. Đây là giao diện web cho thí sinh, không phải dashboard quản trị. Tạo màn hình desktop 1440×900 gọn, đẹp, đáng tin cậy, bằng tiếng Việt.

## Mục tiêu

Trên laptop, toàn bộ vùng làm việc chính nằm trong một viewport, không cuộn toàn trang; chỉ lịch sử hội thoại được cuộn bên trong. Ô nhập luôn cố định ở đáy khung chat.

Phong cách nền sáng trắng/ghi ấm, chữ navy/than dễ đọc, đỏ HUST tiết chế cho CTA và trạng thái; phân cấp rõ, ít thẻ, không gradient, không banner quảng cáo, không số liệu tự bịa.

## Header

Header cao 56–64px gồm logo X, “Trợ lý tuyển sinh X”, “HUST · 2026”; các liên kết “Tài liệu”, “Yêu cầu của tôi”, “Đăng nhập”.

## Bố cục desktop

Bố cục hai cột: trái 280–300px cho ngữ cảnh, phải là hội thoại rộng.

Cột trái có tiêu đề “Tra cứu tuyển sinh”; bộ chọn có tìm kiếm “IT1 · Khoa học Máy tính” (68 chương trình, gợi ý nhóm theo lĩnh vực); bốn lối tắt “Phương thức xét tuyển”, “Học phí & lệ phí”, “Điều kiện ngoại ngữ”, “Quy trình đăng ký”; liên kết “Tài liệu tuyển sinh 2026 · 51 trang — Mở PDF”; nút phụ “So sánh chương trình”.

Cột chat có tiêu đề “Hỏi đáp tuyển sinh”, chip phạm vi “Toàn trường / IT1 · Có thể đổi”, câu hỏi “Học phí IT1 là bao nhiêu?” và câu trả lời:

> Theo tài liệu tuyển sinh 2026, học phí dự kiến của IT1 (chương trình chuẩn) là 28–40 triệu đồng/năm học. Mức thực tế có thể thay đổi theo quy định từng năm.

Gắn nguồn ngay dưới: “Nguồn · PDF trang 20”; các thao tác “Hữu ích”, “Chưa đúng”, “Chuyển câu hỏi cho cán bộ”.

Composer có placeholder “Đặt câu hỏi tuyển sinh…” và nút đỏ “Gửi”. Disclaimer: “Trợ lý tham khảo tài liệu, không quyết định trúng tuyển.” Không thêm tải tệp vì sản phẩm chưa hỗ trợ.

## Responsive

Tablet chuyển chọn ngành/lối tắt thành drawer thu gọn. Điện thoại một cột, không cuộn ngang; selector mở bottom sheet, câu hỏi nhanh thành chip, composer sticky có safe area.

Thiết kế như giao diện production thực tế, căn lề chính xác, dễ đọc, vừa màn hình; không thêm mobile mockup.

## Prompt bổ sung — đồng bộ cán bộ và quản trị

Preview đang hiện “No changes”, còn Diff chỉ có `app/page.tsx`; hãy sửa trực tiếp mã project để tạo các trang giao diện đồng bộ với trang user hiện tại: `app/staff/page.tsx`, `app/staff/login/page.tsx`, `app/admin/page.tsx`, `app/admin/login/page.tsx` và stylesheet dùng chung. Dùng header X/HUST, nền trắng và ghi ấm, navy, đỏ HUST tiết chế, header gọn; khung chính vừa viewport 1440×900 và chỉ cuộn bên trong danh sách dài.

Trang cán bộ có hàng chờ, tìm/lọc, chi tiết, nhận và phản hồi ticket. Trang admin có tổng quan, ticket, cán bộ và phân công. Gắn nút đăng nhập cán bộ/admin ở trang user. Không bịa số liệu; trạng thái rỗng phải nói rõ chưa có dữ liệu. Hoàn tất sửa mã, rồi xác nhận bằng danh sách file thật trong Diff và trạng thái Preview.
