# Báo cáo chuẩn hóa K71 — nhập học 2026

Nguồn: 6 PDF; trang: 131; bảng: 79; bản ghi: 1132; chunks: 1065.

Hiệu lực K71 được chủ dự án xác nhận. Không gán năm 2026 cho dữ liệu điểm chuẩn lịch sử 2024/2025.

## Nhóm dữ liệu

| Nhóm | Bản ghi (có thể thuộc nhiều nhóm) |
|---|---:|
| admission_rules | 350 |
| application_steps | 93 |
| contacts | 21 |
| cutoffs | 377 |
| enrollment_rules | 13 |
| exam_rules | 155 |
| institutional_rules | 55 |
| language_rules | 207 |
| programs | 196 |
| scholarships | 2 |
| scoring_rules | 101 |
| student_support | 60 |
| training_models | 24 |
| tuition_rules | 63 |

## Các giới hạn cần xử lý

- Catalog là nguồn metadata chung; PDF gốc không đổi. Không ghi đè sources.md.
- OCR và bảng gộp/tiếp nối giữ trạng thái cần đối chiếu; raw grids không đưa vào chunks trả lời.
- Native sections và chương trình đủ cấu trúc để phát triển; chưa thay thế duyệt nội dung của cán bộ.
- normalized/*.jsonl là bản ghi có nguồn theo chủ đề, không phải toàn bộ bảng đã chuyển thành giá trị tính toán.
- Dữ kiện web tóm tắt từ main được giữ riêng trong admissions_facts_2026.json; chưa có bản lưu web đầy đủ. Điểm chuẩn trong records.jsonl là lịch sử 2024/2025.
- Không suy ra tổng học phí năm từ đơn giá TCHP, không tính điểm từ công thức OCR chưa duyệt.

## Vấn đề phát hiện

- `toc_excluded` / hust-regulations-k71 / trang 3: Mục lục lưu trong extracted, không làm bằng chứng trả lời.
- `ocr_requires_visual_review` / hust-tsa-k71 / trang 1: OCR confidence=93; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
- `ocr_requires_visual_review` / hust-tsa-k71 / trang 2: OCR confidence=94; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
- `ocr_requires_visual_review` / hust-tsa-k71 / trang 3: OCR confidence=94; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
- `ocr_requires_visual_review` / hust-tsa-k71 / trang 4: OCR confidence=94; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
- `ocr_requires_visual_review` / hust-tsa-k71 / trang 5: OCR confidence=94; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
- `ocr_requires_visual_review` / hust-tsa-k71 / trang 6: OCR confidence=95; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
- `ocr_requires_visual_review` / hust-tsa-k71 / trang 7: OCR confidence=95; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
- `ocr_requires_visual_review` / hust-tsa-k71 / trang 8: OCR confidence=95; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
- `ocr_requires_visual_review` / hust-tsa-k71 / trang 9: OCR confidence=95; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
- `ocr_requires_visual_review` / hust-tsa-k71 / trang 10: OCR confidence=95; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
- `ocr_requires_visual_review` / hust-tsa-k71 / trang 11: OCR confidence=95; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
- `ocr_requires_visual_review` / hust-tsa-k71 / trang 12: OCR confidence=94; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
- `ocr_requires_visual_review` / hust-tsa-k71 / trang 13: OCR confidence=95; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
- `ocr_requires_visual_review` / hust-tsa-k71 / trang 14: OCR confidence=95; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
- `ocr_requires_visual_review` / hust-tsa-k71 / trang 15: OCR confidence=94; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
- `ocr_requires_visual_review` / hust-tsa-k71 / trang 16: OCR confidence=95; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
- `ocr_requires_visual_review` / hust-tsa-k71 / trang 17: OCR confidence=95; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
- `ocr_requires_visual_review` / hust-tsa-k71 / trang 18: OCR confidence=94; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
- `ocr_requires_visual_review` / hust-tsa-k71 / trang 19: OCR confidence=94; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
- `ocr_requires_visual_review` / hust-admissions-k71 / trang 17: OCR confidence=58; kiểm tra chữ, số, công thức và bố cục bảng trước dùng làm kết luận.
