# Tóm tắt tính năng AI, PWA và tính điểm

## 1. AI

- Chatbot tuyển sinh trả lời câu hỏi bằng dữ liệu tuyển sinh đã chuẩn hóa trong `data/`, có manifest phiên bản và kiểm soát nguồn.
- Luồng trả lời dùng tìm kiếm tài liệu (BM25, có thể dùng hybrid khi có bộ máy vector), sau đó mới tạo câu trả lời. Mỗi câu trả lời có nguồn/trích dẫn để người dùng kiểm tra lại.
- Khi không đủ căn cứ hoặc câu hỏi vượt phạm vi, hệ thống hướng người dùng chuyển câu hỏi cho cán bộ thay vì tự đoán.
- AI dùng để hiểu câu hỏi, tìm đúng thông tin và diễn đạt dễ đọc; công thức điểm và dữ liệu điểm chuẩn do mã nghiệp vụ và dữ liệu nguồn quyết định, không để AI tự tính.
- Quản trị viên có màn hình theo dõi chất lượng AI, phiên bản dữ liệu và trạng thái nguồn.

## 2. PWA và giao diện mobile

- Website đã có giao diện responsive, thẻ `viewport`, bố cục riêng cho màn hình nhỏ và hỗ trợ các luồng sinh viên, cán bộ, admin trên trình duyệt.
- CSS đã xử lý các vùng dễ tràn ngang như header, bảng, modal, tab và thanh nhập chat; các vùng dữ liệu dài được cuộn trong khối phù hợp.
- Hiện project chưa có `manifest.webmanifest` và service worker/cache offline. Vì vậy đây là web responsive, chưa phải PWA cài đặt hoàn chỉnh. Muốn bật đầy đủ PWA cần bổ sung manifest, icon, service worker và chiến lược cache an toàn.

## 3. Tính điểm và đối chiếu nguyện vọng

- **THPT:** nhập điểm Toán và hai môn trong tổ hợp; hệ thống áp dụng hệ số theo chương trình, quy đổi IELTS cho các tổ hợp có tiếng Anh, cộng điểm khu vực/đối tượng và giới hạn thang điểm theo quy định.
- **TSA:** nhập điểm TSA, IELTS và ưu tiên; IELTS được quy đổi thành điểm thưởng theo bảng, không thay thế điểm TSA.
- **XTTN 1.2:** hỗ trợ SAT, ACT, A-Level, AP, IB; IELTS là điểm thưởng và được quy đổi về đúng thang của chứng chỉ chính.
- **XTTN 1.3:** nhập TSA, điểm thành tích, điểm thưởng khác và IELTS; hệ thống tính theo tỷ trọng TSA 40/60, thành tích tối đa 50 và điểm thưởng tối đa 10.
- Có gợi ý ngay tại trường nhập liệu về việc môn nào nhân hệ số, IELTS được dùng ở phương thức nào và thang điểm tương ứng; người dùng không phải tự mở bảng công thức.
- Người dùng có thể thêm, xóa và sắp xếp nguyện vọng. Kết quả hiển thị điểm tính được, điểm chuẩn tham khảo và mức chênh lệch để dễ nhận biết cơ hội.
- Dữ liệu điểm chuẩn là dữ liệu tham khảo theo năm và phương thức, không phải cam kết đỗ. Chứng chỉ IELTS vẫn phải đáp ứng điều kiện xác thực của trường; các điểm thành tích do người dùng nhập cần có hồ sơ chứng minh khi đăng ký chính thức.

## Kiểm tra kỹ thuật gần nhất

- Test API tính điểm: **17 passed**.
- Kiểm tra cú pháp JavaScript, biên dịch Python và `git diff --check`: **đạt**.
- Chưa triển khai hoặc gửi email thật; chưa thay đổi dữ liệu production.
