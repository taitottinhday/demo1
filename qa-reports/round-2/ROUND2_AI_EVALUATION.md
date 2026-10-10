# Đánh giá câu trả lời AI — vòng 2

## Phạm vi và số liệu

`ROUND2_AI_ACCURACY.csv` có **150 câu hỏi** chia thành các nhóm: phương thức/điều kiện (25), mã và tên chương trình (25), học phí/lệ phí (20), chỉ tiêu/điểm/tổ hợp (15), TSA (15), ngoại ngữ (15), hội thoại nhiều lượt/race (15), câu mơ hồ/nhiều ý (10), ngoài phạm vi/không đủ dữ liệu/an toàn (10).

Trong số này:

- **4** câu chạy cục bộ bằng knowledge corpus trích xuất: IT2 phương thức, tên IT1, học phí IT1 theo năm, chỉ tiêu IT1.
- **1** câu trả lời AI đã có sẵn trong ticket production được đối chiếu: chỉ tiêu IT2 = 200, nguồn PDF trang 10. Đây là bản ghi production có sẵn, không phải câu hỏi được gửi thêm trong audit.
- **145** câu chưa chạy.
- Không đo latency và không tính accuracy tổng thể. Năm trường hợp có thể đối chiếu không phải mẫu ngẫu nhiên/đủ lớn.

Các kịch bản TSA chưa có câu trả lời ground truth đã OCR vì quy chế trong repo là scan; tiêu chí đúng là không suy đoán lịch, lệ phí hoặc quy trình không truy xuất được. Quy định ngoại ngữ được đánh giá theo đúng đối tượng áp dụng; không biến chính sách sinh viên K71 thành điều kiện tuyển sinh chung.

## Kết quả có bằng chứng

- 4/4 câu local đã chạy trả đúng fact trích xuất và source/page được gắn trong CSV.
- 1/1 câu quota trên ticket có sẵn khớp dữ liệu: mã IT2, chỉ tiêu 200, nguồn tuyển sinh 2026. Ticket admin còn giữ citation PDF trang 10.
- Mẫu “Gợi ý ngành” trực tiếp không tự tạo phần trăm phù hợp; lý do nêu tiêu chí người dùng nhập và chỉ kết luận trong giới hạn corpus.

Không cộng các mẫu khác nhau thành một accuracy percentage; câu ticket là câu trả lời production có sẵn, còn bốn câu là câu chạy cục bộ. Đây không phải benchmark đầy đủ của model.

## Coverage còn thiếu

Không thực hiện 150 lượt hỏi trên production để tránh phát sinh tải và lịch sử thử nghiệm. 20 kịch bản hội thoại nhiều lượt (5–10 turns) trong [ROUND2_TEST_CASES.csv](ROUND2_TEST_CASES.csv) đều `NOT_TESTED`; 15 dòng chain trong CSV accuracy cũng chỉ là fixture chưa chạy. Tiếp theo nên chạy trên staging hoặc một fixture session độc lập, chấm từng claim theo nguồn chính thức và lưu latency/citation separately.
