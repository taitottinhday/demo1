# Đánh giá rủi ro và sẵn sàng phát hành

## Quyết định

**NO-GO tạm thời** cho phát hành rộng, vì kiểm thử chưa đủ độ phủ và full test suite chưa xanh. Không có bug production mới nghiêm trọng được tái lập trong vòng 2.

| Mức | Rủi ro | Bằng chứng | Việc tiếp theo |
|---|---|---|---|
| Cao | Sai câu trả lời hoặc mất citation ở các cách hỏi chưa chạy | 145/150 câu AI chưa chạy; 20 luồng đa lượt chưa chạy | Chạy benchmark trên staging; kiểm từng claim và source/page |
| Cao | Không xác minh được phía thí sinh nhận phản hồi | Cán bộ/admin xác nhận đã gửi; session thí sinh sở hữu không có sẵn | Tạo fixture E2E session cô lập và kiểm tra đúng owner |
| Trung bình | Hồi quy quota dài chưa được tái lập production sau thay đổi router | Unit quota pass; production record đúng, nhưng câu hỏi dài chưa gửi lại | Thêm biến thể dài/ngắn/dấu tiếng Việt vào kiểm thử staging |
| Trung bình | Suite đỏ | 94 passed, 1 failed do test LLM quote không khớp đường deterministic đang chạy | Xác nhận hợp đồng và sửa test/router để suite xanh |
| Trung bình | Lỗi lint tồn tại | 3 lỗi Ruff trong source/test | Sửa và thêm lint vào CI |
| Trung bình | Rủi ro an ninh chưa lượng hóa | 27 test auth/admin/data pass; API/security production chưa kiểm tra | Security review trên staging, bao gồm role guard và session |
| Thấp | Tablet breakpoint chưa xác minh đầy đủ | 768×1024 không tràn ngang nhưng chưa chắc drawer mở đúng | Kiểm tra bằng viewport/device thật |

## Điều kiện để nâng GO

1. Full test suite và lint xanh, hoặc ngoại lệ được giải thích bằng quyết định kỹ thuật có review.
2. Hoàn thành AI benchmark có phân tầng, citations, abstention và test đa lượt trên môi trường an toàn.
3. E2E xác nhận phản hồi hiện cho đúng session thí sinh sở hữu ticket.
4. Security test API và role permissions được chạy độc lập khỏi UI.
5. Hoàn thành tablet/accessibility và network/latency measurement.

Không suy rộng kết quả audit hiện tại thành bảo đảm về độ chính xác hay bảo mật production.
