# Weekly Journal — Team [Tên Team]

> Ghi lại mỗi tuần: học được gì, khó khăn gì, quyết định gì, kế hoạch tiếp.

---

## Week 1: [Ngày bắt đầu] - [Ngày kết thúc]

### Mục tiêu tuần này
- [ ] [Mục tiêu 1]
- [ ] [Mục tiêu 2]
- [ ] [Mục tiêu 3]

### Đã hoàn thành
- [thành quả 1]
- [thành quả 2]

### Khó khăn & Giải pháp
| Khó khăn | Giải pháp | Kết quả |
|----------|-----------|---------|
| [mô tả] | [cách xử lý] | [output] |

### Bài học
- [bài học 1]
- [bài học 2]

### Kế hoạch tuần sau
- [ ] [task 1]
- [ ] [task 2]

---

## Week 2: [Ngày bắt đầu] - [Ngày kết thúc]

### Mục tiêu tuần này
- [ ] [Mục tiêu 1]

### Đã hoàn thành
-

### Khó khăn & Giải pháp
| Khó khăn | Giải pháp | Kết quả |
|----------|-----------|---------|
| | | |

### Bài học
-

### Kế hoạch tuần sau
-

---

<!-- Tiếp tục copy block trên cho Week 3, 4, 5, 6 -->

## Nhật ký công việc — 2026-10-15

- Bỏ polling định kỳ gây nháy ở chat/ticket và bảng cán bộ/admin; giữ thao tác làm mới thủ công.
- Sửa breakpoint mobile bị stylesheet tải sau ghi đè; đặt cỡ chữ input tối thiểu 16px trên mobile để tránh Safari tự zoom khi focus.
- Bổ sung email thông báo sau khi lưu phản hồi, lưu trạng thái gửi riêng, chỉ dùng email tài khoản đã xác minh và thêm gửi lại thông báo lỗi.
- Tạo nút vào demo cán bộ/admin cho `development`/`test`; API demo bị tắt trong `production`.
- Giới hạn hiện tại: tác vụ email nền dùng FastAPI BackgroundTasks, chưa có hàng đợi bền vững. Chưa deploy/push/commit; kiểm thử không dùng email thật.
