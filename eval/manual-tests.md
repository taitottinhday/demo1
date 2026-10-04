# Gate 2 — Báo cáo kiểm tra 6 ca hỏi đáp với output thực tế

**Sản phẩm:** Trợ lý tuyển sinh X — HUST 2026 · EDU-12.

**Môi trường:** ứng dụng local `http://127.0.0.1:8000`, chế độ `extractive`, PDF tuyển sinh 51 trang do nhóm cung cấp. Không gọi LLM trong các ca này.

**Thời điểm ghi output:** 04/10/2026, 21:04:47 (UTC+7).

**Phương pháp:** Nhóm gửi từng câu hỏi trực tiếp đến ứng dụng local và ghi nhận output thực tế. Codex được sử dụng để hỗ trợ tổng hợp và đối chiếu kết quả với nguồn.

**Người thực hiện đối chiếu:** trợ lý AI Codex. Các kết luận dưới đây là kết quả đối chiếu có hỗ trợ AI, không phải chữ ký người kiểm tra. Không dùng báo cáo này để tuyên bố đạt accuracy ≥85%.

## Tổng hợp

| Ca | Nội dung | Kết luận đối chiếu |
|---|---|---|
| M01 | Chỉ tiêu IT1 | Đạt: đúng 300, đúng nguồn |
| M02 | Học phí ET1 | Đạt: đúng nhóm chuẩn, mức dự kiến và đơn vị |
| M03 | Phương thức IT1 | Đạt: đủ ba phương thức và tổ hợp |
| M04 | Ngoại ngữ ITE10 | Đạt: đúng điều kiện thay thế nhau, đúng chương trình |
| M05 | Đăng ký ký túc xá | Đạt: không dùng hướng dẫn ĐGTD thay thế |
| M06 | Tuyển giảng viên | Đạt: ngoài phạm vi, không khẳng định tình trạng tuyển dụng |

**Cách chạy lại trên giao diện:** khởi động theo [README MVP](../README-MVP.md), chọn “Chưa chọn chương trình”, nhập input từng ca và gửi. Với M01–M04, mở nguồn để đối chiếu; với M05–M06, kiểm tra không có trích dẫn không liên quan. Sáu ca chỉ đánh giá các hành vi cụ thể này, không đại diện cho toàn bộ câu hỏi tuyển sinh.

## M01 — Chỉ tiêu chương trình IT1

**Câu hỏi:** `IT1 co chi tieu bao nhieu?`

**Kỳ vọng:** IT1 có chỉ tiêu 300; nguồn trang PDF 10.

**HTTP và trạng thái thực tế:** 200; kind: answered; reason: grounded

**Output thực tế (giữ nguyên):**

```text
Mã xét tuyển IT1: CNTT: Khoa học Máy tính. [1]

Chỉ tiêu năm 2026: 300. [1]
```

**Trang PDF nguồn:** 10

**Mã truy vết:** `915c5090ba0e300a`

**Kết luận đối chiếu:** Đạt theo tiêu chí của ca kiểm tra; phương pháp và phạm vi nêu ở đầu báo cáo.

**Đối chiếu bởi:** trợ lý AI Codex, ngày 04/10/2026.

## M02 — Học phí chương trình ET1

**Câu hỏi:** `hoc phi cua et1 la bao nhieu`

**Kỳ vọng:** chương trình chuẩn ET1 có học phí dự kiến 28–40 triệu đồng/năm học; nguồn trang PDF 20.

**HTTP và trạng thái thực tế:** 200; kind: answered; reason: grounded

**Output thực tế (giữ nguyên):**

```text
Học phí dự kiến K71 năm học 2026–2027, chương trình chuẩn: Kỹ thuật Điện tử - Viễn thông: 28 - 40 triệu đồng/năm học. Đây là mức trung bình dự kiến, không phải cam kết học phí cá nhân. [1]
```

**Trang PDF nguồn:** 20

**Mã truy vết:** `a3af0e03d5742f59`

**Kết luận đối chiếu:** Đạt theo tiêu chí của ca kiểm tra; phương pháp và phạm vi nêu ở đầu báo cáo.

**Đối chiếu bởi:** trợ lý AI Codex, ngày 04/10/2026.

## M03 — Phương thức xét tuyển IT1

**Câu hỏi:** `phuong thuc xet tuyen nganh IT1`

**Kỳ vọng:** đủ XTTN, ĐGTD và THPT; tổ hợp A00 (Gốc), A01, K01; nguồn trang PDF 10.

**HTTP và trạng thái thực tế:** 200; kind: answered; reason: grounded

**Output thực tế (giữ nguyên):**

```text
IT1 — CNTT: Khoa học Máy tính có các phương thức xét tuyển:

• Xét tuyển tài năng (XTTN). [1]
• Xét tuyển theo kết quả thi Đánh giá tư duy (ĐGTD). [1]
• Xét tuyển theo kết quả thi tốt nghiệp THPT; tổ hợp: A00 (Gốc); A01; K01. [1]
```

**Trang PDF nguồn:** 10

**Mã truy vết:** `6e11423103428d08`

**Kết luận đối chiếu:** Đạt theo tiêu chí của ca kiểm tra; phương pháp và phạm vi nêu ở đầu báo cáo.

**Đối chiếu bởi:** trợ lý AI Codex, ngày 04/10/2026.

## M04 — Ngoại ngữ đầu vào ITE10

**Câu hỏi:** `dieu kien ngoai ngu ITE10`

**Kỳ vọng:** ngoài điều kiện xét tuyển khác, đáp ứng một trong VSTEP B1+, IELTS Academic 5.0+ hoặc tương đương, hoặc điểm tiếng Anh THPT 2026 từ 6.5; nguồn trang PDF 16 và 10.

**HTTP và trạng thái thực tế:** 200; kind: answered; reason: grounded

**Output thực tế (giữ nguyên):**

```text
ITE10 — Khoa học dữ liệu và Trí tuệ nhân tạo (CT tiên tiến): ngoài các điều kiện xét tuyển khác, bạn cần đáp ứng một trong các điều kiện ngoại ngữ đầu vào sau. [2] [1]

• VSTEP B1 trở lên. [1]
• IELTS Academic 5.0 trở lên hoặc tương đương. [1]
• Điểm thi tốt nghiệp THPT 2026 môn tiếng Anh từ 6.5 trở lên. [1]
```

**Trang PDF nguồn:** 16, 10

**Mã truy vết:** `e4b8785c9eeb7679`

**Kết luận đối chiếu:** Đạt theo tiêu chí của ca kiểm tra; phương pháp và phạm vi nêu ở đầu báo cáo.

**Đối chiếu bởi:** trợ lý AI Codex, ngày 04/10/2026.

## M05 — Thiếu nguồn hướng dẫn ký túc xá

**Câu hỏi:** `cach dang ky ktx`

**Kỳ vọng:** báo chưa có hướng dẫn KTX đã xác minh, cho phép chuyển cán bộ; không trả hướng dẫn đăng ký thi thay thế.

**HTTP và trạng thái thực tế:** 200; kind: fallback; reason: guardrail

**Output thực tế (giữ nguyên):**

```text
Bộ nguồn hiện tại chưa có hướng dẫn đăng ký ký túc xá đã được xác minh. Mình không thể dùng quy trình đăng ký xét tuyển để hướng dẫn thuê chỗ ở. Bạn có thể gửi câu hỏi này cho cán bộ để nhờ kiểm tra thông tin ký túc xá.
```

**Trang PDF nguồn:** Không có

**Mã truy vết:** `b6f05bb5f45fefdc`

**Kết luận đối chiếu:** Đạt theo tiêu chí của ca kiểm tra; phương pháp và phạm vi nêu ở đầu báo cáo.

**Đối chiếu bởi:** trợ lý AI Codex, ngày 04/10/2026.

## M06 — Tuyển dụng ngoài phạm vi

**Câu hỏi:** `truong co tuyen giang vien khong`

**Kỳ vọng:** báo ngoài phạm vi tuyển sinh, không khẳng định trường có/không tuyển và không trích bảng ngành.

**HTTP và trạng thái thực tế:** 200; kind: fallback; reason: out_of_scope

**Output thực tế (giữ nguyên):**

```text
Mình hỗ trợ tuyển sinh đại học chính quy HUST 2026, chưa có nguồn về tuyển dụng giảng viên hoặc nhân sự. Bạn cần tra cứu thông báo tuyển dụng chính thức của trường; mình không thể xác nhận trường đang tuyển hay không.
```

**Trang PDF nguồn:** Không có

**Mã truy vết:** `97d7239e5a357a94`

**Kết luận đối chiếu:** Đạt theo tiêu chí của ca kiểm tra; phương pháp và phạm vi nêu ở đầu báo cáo.

**Đối chiếu bởi:** trợ lý AI Codex, ngày 04/10/2026.
