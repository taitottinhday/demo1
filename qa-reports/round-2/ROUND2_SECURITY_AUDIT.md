# Kiểm tra bảo mật — vòng 2

## Những gì đã xác minh

- Trang cán bộ và admin yêu cầu đăng nhập trước khi hiển thị dashboard; đăng nhập đúng bằng thông tin do người dùng cung cấp mở đúng vai trò.
- Các session admin/cán bộ hết hạn trong quá trình audit; đăng nhập lại yêu cầu xác thực và không tự mở dashboard từ session hết hạn.
- Cán bộ chỉ thao tác ticket QA_TEST đã được người dùng cho phép. Không dùng chức năng từ chối, sửa tài khoản, đặt lại mật khẩu hoặc xem thông tin liên hệ cán bộ trong báo cáo.
- Không lưu thông tin đăng nhập vào artifact. Báo cáo không ghi mật khẩu, email hoặc dữ liệu cá nhân ứng viên.
- Các trang web được kiểm tra không có lỗi/warning console được ghi nhận trong mẫu phiên này.

## Chưa kiểm thử

Không thực hiện kiểm thử xâm nhập production, bypass xác thực, IDOR, CSRF, XSS, injection, brute force/rate limit, session fixation, cookie/header, CORS, upload, secret scan trên môi trường chạy, hay quyền truy cập endpoint trực tiếp. Chưa thu network/API request hoặc log server. Kiểm thử bảo mật cục bộ có 27 test auth/admin/data pass nhưng không thay thế security review production.

## Kết luận

Không có lỗi bảo mật production được xác nhận trong phạm vi UI đã xem; **không đủ bằng chứng để kết luận hệ thống an toàn trước phát hành**. Cần chạy bộ security test trên staging với dữ liệu giả lập và xác nhận các role guard/API access độc lập với giao diện.
