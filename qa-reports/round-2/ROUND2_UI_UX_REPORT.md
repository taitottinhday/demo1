# Kiểm tra giao diện và khả năng sử dụng — vòng 2

## Kích thước viewport

| Viewport | Kết quả | Ghi chú |
|---|---|---|
| 1920×1080 | PASS | Không thấy tràn ngang/dọc; composer trong viewport. |
| 1366×768 | PASS | Không thấy tràn ngang/dọc; composer vẫn hiện. |
| 768×1024 | PARTIAL | Không tràn ngang; chưa xác nhận đầy đủ trạng thái drawer/breakpoint tablet. |
| 390×844 | PASS | Không tràn ngang; composer nằm trong viewport. |
| 375×667 | PASS | Không tràn ngang; composer nằm trong viewport. |

Kích thước được kiểm tra bằng viewport override trên IAB; phép override kích thước trong Chrome desktop không ổn định, do đó kết quả tablet không được nâng thành PASS hoàn toàn. Bảng số liệu/giới hạn được ghi tại [evidence/viewport-metrics.csv](evidence/viewport-metrics.csv).

## Những điểm đã kiểm tra

- Trang thí sinh có selector 68 chương trình, bốn shortcut, tài liệu, so sánh và checklist; composer chat cố định trong vùng giao diện.
- Desktop/laptop và các viewport điện thoại được kiểm tra không có cuộn ngang toàn trang.
- Nội dung so sánh IT1/IT2, giải thích gợi ý ngành và checklist hiển thị đúng nguồn trong các luồng đã mở.
- Admin và cán bộ có trạng thái, bộ lọc và thông tin ticket dễ phân biệt; không phát hiện lỗi console trong mẫu.

## Giới hạn

Không đo được Lighthouse/Web Vitals, độ tương phản tự động, bàn phím/screen reader đầy đủ hoặc pixel-perfect ở mọi kích thước. Không lưu được ảnh production thành file trong repo; bằng chứng ảnh ticket đã hiển thị trong phiên audit, các snapshot văn bản đã được làm sạch nằm trong `evidence/`.
