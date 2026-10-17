# AI/RAG: xử lý rủi ro và việc còn cần xác minh

Cập nhật: 17/10/2026. Tài liệu này ghi nhận việc sửa trong repository và các điểm không thể xác nhận chỉ bằng kiểm tra tự động.

## Đã xử lý trong mã và bộ đánh giá

- Sửa bộ chấm golden để một nguồn tương đương chỉ được chấp nhận khi khai báo rõ cho đúng nguồn kỳ vọng; vẫn bắt buộc các nguồn độc lập còn lại. Ca phương thức tuyển sinh 2026 cho phép đối chiếu cả Quy chế và Đề án tuyển sinh chính thức.
- Làm rõ ca học phí IT1 hỏi đơn giá cho mỗi TCHP trong năm học 2026–2027. Đáp án vẫn phân biệt đơn giá tín chỉ với tổng học phí phải đóng.
- Lưu `generation_guard_reason` cùng bước `generation_check` vào từng dòng báo cáo eval. Lần chạy mới sẽ phân biệt được lỗi schema, trích dẫn, số liệu, guardrail và các bước khác; không cần ghi nội dung prompt/response riêng để chẩn đoán.
- Cập nhật tài liệu và metadata release để phản ánh adapter records/chunks hiện đã được runtime tích hợp, BM25 mặc định và hybrid là cấu hình tùy chọn.
- Thêm kiểm thử bảo đảm nguồn tương đương không làm yếu yêu cầu nguồn và bộ chấm vẫn yêu cầu mọi nguồn độc lập.

## Rủi ro được giữ chặn cho an toàn

- OCR TSA (19 trang) và bảng ngoại ngữ trang PDF 17 cần người đối chiếu với ảnh/PDF gốc. Các bản ghi này chưa được dùng để tự kết luận; không nâng `answer_eligible` hoặc `staff_reviewed` bằng tự động hóa.
- Các bản ghi được trích xuất kỹ thuật không đồng nghĩa đã được cán bộ tuyển sinh duyệt. Chỉ người phụ trách nội dung mới có thể xác nhận điều kiện, năm áp dụng, đơn vị và ngoại lệ.
- Chi tiết từng học bổng còn thiếu trong corpus; không suy điều kiện hay quyền lợi từ trang danh mục.
- Golden 20 ca và retrieval development 25 ca là bộ phát triển, không phải holdout độc lập. Điểm khớp nhãn tự động không phải độ chính xác đã được con người xác nhận.
- Lần đánh giá DeepSeek trước có 8/18 câu nghiệp vụ được chấp nhận và 10/18 fallback do grounding; hiện không có DeepSeek credential trong môi trường local để tái hiện đúng provider. Chưa thể kết luận nguyên nhân từng fallback hay xác nhận cải thiện sau sửa chỉ bằng mock.

## Việc cần làm trước khi tuyên bố chất lượng nội dung

1. Cán bộ tuyển sinh đối chiếu 19 trang TSA và trang ngoại ngữ PDF 17; ghi reviewer, ngày, trang, sai khác và nguồn gốc. Sau review, cập nhật dữ liệu có kiểm soát rồi chạy validator và đóng checksum snapshot.
2. Cán bộ xác nhận các dữ kiện tuyển sinh/học phí theo năm, các trường hợp ngoại lệ và nguồn web tóm tắt; lưu trữ bản nguồn có ngày truy cập.
3. Bổ sung tài liệu chính thức cho từng học bổng cần hỗ trợ, bao gồm đối tượng, điều kiện, mức và thời gian; nếu chưa có thì giữ câu trả lời từ chối/tra cán bộ.
4. Tách một holdout do người khác soạn, chấm độc lập câu trả lời và trích dẫn theo tiêu chí đúng ý, đủ phạm vi/năm/đơn vị, và bằng chứng thực sự hỗ trợ kết luận.
5. Chạy lại golden trên môi trường test có cấu hình DeepSeek sau khi sửa, dùng output riêng; kiểm tra tỷ lệ trả lời, lý do fallback, trích dẫn, latency và token. Không gửi dữ liệu production hoặc email thật.

## Không được kết luận từ lần sửa này

Không xác nhận chất lượng nội dung 100%, không xác nhận DeepSeek đã hết fallback, không chứng nhận OCR, không xác nhận email/provider production và không coi thay đổi metadata/checksum là bằng chứng duyệt học thuật.
