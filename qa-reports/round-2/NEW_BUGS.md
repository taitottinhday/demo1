# Lỗi mới phát hiện trong vòng 2

**Không có lỗi chức năng production mới được xác nhận.**

Các giới hạn và việc chưa hoàn tất được theo dõi riêng như sau:

- `R2-E2E-01` — **PARTIAL**: cán bộ và admin xác nhận phản hồi cùng trạng thái đã giải quyết; các phiên thí sinh hiện mở không phải phiên sở hữu ticket, nên không thấy yêu cầu. Không thể xác minh màn hình của đúng chủ ticket từ phiên hiện tại.
- `R2-API-01` — **BLOCKED**: không thu được HTTP status, lỗi network hoặc p95 qua browser connector.
- `R2-LOCAL-02` — **FAIL**: một test cục bộ đỏ; xem [REGRESSION_BUGS.md](REGRESSION_BUGS.md).
- `R2-LOCAL-04` — **FAIL**: ba lỗi lint; xem [REGRESSION_BUGS.md](REGRESSION_BUGS.md).
- `R2-CHAT-02` — **PARTIAL**: conversation gốc có ba cặp trùng không truy cập lại được để so ID.
- `R2-UI-04` — **PARTIAL**: tại 768×1024 không xác minh đầy đủ trạng thái drawer.

Các mục này là thiếu bằng chứng hoặc lỗi kiểm tra cục bộ, không phải bug production đã tái lập.
