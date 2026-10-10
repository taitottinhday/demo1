# Kiểm toán dữ liệu tuyển sinh — vòng 2

## Corpus đã kiểm tra

- Manifest `data/sources.md` liệt kê 8 nguồn tuyển sinh/học tập.
- Giao diện production hiển thị 68 chương trình; PDF tuyển sinh chính là 51 trang; 5 PDF có thể truy xuất trong app.
- `data/normalized/admissions_facts_2026.json` chứa 17 fact đã chuẩn hóa để đối chiếu.
- Câu trả lời so sánh và ticket test trỏ đúng tài liệu tuyển sinh 2026; quota IT1/IT2 ở trang 10 và học phí năm ở trang 20.

## Quy tắc diễn giải an toàn

1. Tách quota, phương thức, tổ hợp, điểm chuẩn và năm tuyển sinh; không thay câu hỏi quota bằng câu trả lời phương thức.
2. Học phí theo năm và đơn giá/TCHP là hai phạm vi khác nhau. Không tính tổng nếu không có số tín chỉ và căn cứ đủ rõ.
3. Quy định ngoại ngữ K71 áp dụng cho nhóm sinh viên nêu trong văn bản; không dùng làm điều kiện đầu vào chung của mọi thí sinh.
4. Điểm chuẩn cũ không được suy diễn thành điểm chuẩn 2026 nếu nguồn không công bố.
5. Mục học bổng trên web không đủ chi tiết để khẳng định mức/điều kiện từng học bổng; cần dẫn trang chính thức hoặc chuyển cán bộ.
6. Quy chế TSA trong corpus là scan chưa OCR/đối chiếu; các câu hỏi lịch, hạn, lệ phí và quy trình cụ thể cần abstain hoặc hỏi nguồn cập nhật.

## Đánh giá chất lượng mẫu

Các câu được chạy trong vòng này khớp facts đã chuẩn hóa. Chưa có kiểm toán trọn vẹn 68 chương trình, đủ 8 tài liệu hoặc so sánh mọi bảng gốc với PDF. CSV 150 câu chỉ là ma trận ground truth/test status; 145 câu còn lại chưa được gửi chạy, nên không đại diện độ chính xác thực tế.

## Rủi ro dữ liệu cần theo dõi

- Phiên bản nguồn production hiển thị hash `6991e9023c3e…`; nên lưu manifest + checksum tài liệu dùng khi deploy để phát hiện nguồn thay đổi.
- Ghi rõ ngày hiệu lực, đối tượng, chương trình, đơn vị tiền và trang nguồn cho từng fact.
- Thêm kiểm tra tự động để câu quota chứa đúng mã/năm và không rơi sang intent phương thức khi thay đổi diễn đạt.
