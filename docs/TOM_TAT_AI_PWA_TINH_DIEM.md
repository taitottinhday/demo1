# Tóm tắt triển khai: AI, giao diện mobile và tính điểm

Tài liệu này mô tả ngắn gọn ba nhóm chức năng chính đã triển khai trong project, cách hệ thống vận hành và các giới hạn cần lưu ý khi demo hoặc bàn giao.

## 1. AI tuyển sinh

### Mục đích

Hỗ trợ sinh viên tra cứu thông tin tuyển sinh bằng ngôn ngữ tự nhiên, giảm thời gian tìm trong nhiều tài liệu và chuyển cán bộ khi câu hỏi cần xử lý thủ công.

### Cách triển khai

1. Tài liệu tuyển sinh được chuẩn hóa thành các đoạn dữ liệu trong `data/`.
2. Mỗi nguồn có manifest, phiên bản và thông tin kiểm soát để biết câu trả lời đang dựa trên bộ dữ liệu nào.
3. Hệ thống tìm các đoạn liên quan bằng BM25; khi môi trường có bộ máy vector thì sử dụng chế độ hybrid, nếu không sẽ tự động fallback về BM25.
4. Mô hình AI dùng kết quả truy hồi để diễn đạt câu trả lời, kèm nguồn/trích dẫn và bước tiếp theo.
5. Nếu không đủ căn cứ, câu hỏi ngoài phạm vi hoặc có rủi ro tư vấn sai, hệ thống hướng sinh viên chuyển câu hỏi cho cán bộ.

### Nguyên tắc dữ liệu

- AI không tự quyết định điểm chuẩn, công thức xét tuyển hay kết quả đỗ/trượt.
- Công thức điểm được xử lý bằng mã nghiệp vụ; câu trả lời phải dựa trên dữ liệu nguồn đã lập chỉ mục.
- Nội dung trả lời có thể kiểm tra lại qua nguồn và phiên bản tài liệu.
- Quản trị viên có thể theo dõi trạng thái dữ liệu và đánh giá chất lượng trả lời.

## 2. Giao diện mobile và nền tảng PWA

### Những gì đã có

- Giao diện responsive cho sinh viên, cán bộ và admin.
- Thẻ `viewport`, bố cục mobile, header gọn, modal và vùng dữ liệu có cuộn riêng.
- Đã xử lý các lỗi thường gặp trên màn hình nhỏ: tràn ngang, tab bị cắt, nút chồng lấp và thanh nhập chat khó thao tác.
- Các vùng thao tác chính vẫn sử dụng được bằng bàn phím và có trạng thái focus.

### Trạng thái PWA

Hiện project là web responsive, chưa phải PWA hoàn chỉnh vì chưa có `manifest.webmanifest`, service worker và bộ nhớ đệm offline. Nếu cần cài đặt như ứng dụng, bước tiếp theo là bổ sung manifest, icon chuẩn, service worker và chiến lược cache phù hợp với dữ liệu động.

## 3. Tính điểm và đối chiếu nguyện vọng

### Phương thức hỗ trợ

- **THPT:** nhập điểm các môn trong tổ hợp, hệ số môn, khu vực/đối tượng ưu tiên và IELTS nếu tổ hợp có tiếng Anh. Hệ thống tự gợi ý môn nhân hệ số và quy đổi IELTS theo bảng cấu hình.
- **TSA:** nhập điểm TSA, IELTS và ưu tiên. IELTS được tính là điểm thưởng, không thay thế điểm TSA.
- **XTTN 1.2:** hỗ trợ SAT, ACT, A-Level, AP và IB; IELTS được quy đổi về thang của chứng chỉ chính theo công thức tương ứng.
- **XTTN 1.3:** nhập TSA, điểm thành tích, điểm thưởng khác và IELTS; hệ thống áp dụng tỷ trọng TSA 40/60, điểm thành tích tối đa 50 và điểm thưởng tối đa 10.

### Luồng sử dụng

1. Người dùng chọn phương thức xét tuyển.
2. Giao diện chỉ hiển thị các trường dữ liệu phù hợp với phương thức đó.
3. Hệ thống kiểm tra phạm vi, định dạng và giới hạn điểm trước khi tính.
4. Người dùng thêm, xóa hoặc sắp xếp nguyện vọng.
5. Kết quả hiển thị điểm tính được, điểm chuẩn tham khảo và mức chênh lệch để dễ nhận biết ngành đang cao hơn hoặc thấp hơn mốc tham chiếu.

### Giới hạn sử dụng

Điểm chuẩn và quy đổi là dữ liệu tham khảo theo năm/phương thức, không phải cam kết trúng tuyển. IELTS phải đáp ứng điều kiện xác thực của trường; điểm thành tích và thông tin chứng chỉ do người dùng nhập cần được kiểm tra bằng hồ sơ khi đăng ký chính thức.

## 4. Kiểm tra kỹ thuật

- Test API tính điểm: **17 passed**.
- Kiểm tra cú pháp JavaScript, biên dịch Python và `git diff --check`: **đạt**.
- Chưa gửi email thật, chưa thay đổi dữ liệu production và chưa triển khai PWA offline.
