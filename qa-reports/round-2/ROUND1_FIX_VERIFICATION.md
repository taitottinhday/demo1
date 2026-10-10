# Xác minh các lỗi vòng 1

| Hạng mục | Bằng chứng vòng 2 | Kết quả |
|---|---|---|
| BUG-001 — câu hỏi dài về chỉ tiêu IT2 bị hiểu thành phương thức | Regression quota cục bộ pass; câu hỏi trên ticket production được trả lời là IT2 = 200, nguồn PDF trang 10. Không gửi lại chính câu dài vào production trong vòng này. | **PARTIALLY VERIFIED** |
| BUG-002 — ba bản trùng của một cặp hỏi–đáp trong lịch sử | Test cục bộ về idempotency/history nằm trong nhóm chạy; lịch sử của session production đang mở không tăng bong bóng sau reload/refetch. Không còn quyền truy cập đúng conversation/session chứa ba bản gốc và không lấy được ID production. | **PARTIALLY VERIFIED** |
| CTA “Mở cổng đăng ký” nhưng mở PDF | Live checklist đã dùng nhãn “Xem điều kiện trong PDF”/“Mở PDF trang 18”; hai cổng bên ngoài có nhãn đúng, URL chính thức, `target=_blank` và `rel=noopener`. | **VERIFIED FIXED** |
| Giải thích “Gợi ý ngành” chung chung, không cho thấy tiêu chí | Dữ liệu thử được ánh xạ sang lý do cho từng ngành; mục tiêu phát triển không bị trừ điểm; tiêu chí thiếu dữ liệu ghi “Chưa đủ dữ liệu để đối chiếu”; không hiện điểm/phần trăm phù hợp. | **VERIFIED IN SAMPLE** |
| KPI tỷ lệ chuyển cán bộ từng vượt 100% | Admin hiện không hiển thị tỷ lệ này; hiển thị số ticket tạo trong khoảng lọc. Các chỉ số tỷ lệ khác có công thức và tử/mẫu; lọc ngày 08–09/10 cho khoảng kết thúc độc quyền 10/10 00:00 +07. | **VERIFIED FIXED IN CURRENT UI** |

## Giới hạn

Các kết quả “verified” chỉ áp dụng cho phiên và mẫu quan sát trong ngày 10/10/2026. Chúng không thay thế kiểm tra log/API hoặc hồi quy toàn bộ dữ liệu production. Xem [ROUND2_TEST_CASES.csv](ROUND2_TEST_CASES.csv) để biết phạm vi cụ thể; phần mô tả vòng 1 nằm ở [BUG_REPORT.md](../BUG_REPORT.md).
