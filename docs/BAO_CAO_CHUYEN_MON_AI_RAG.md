# Cập nhật AI tuyển sinh — 17/10/2026

## Đã triển khai

- Tích hợp RAG: tìm thông tin trong tài liệu tuyển sinh rồi mới đưa ngữ cảnh cho DeepSeek/OpenAI tổng hợp; không huấn luyện lại mô hình.
- Có BM25 mặc định và hybrid retrieval tùy chọn; câu trả lời giữ nguồn/trang, kiểm tra quote, số liệu và mã ngành. Không đủ căn cứ thì fallback hoặc chuyển cán bộ.
- Dữ liệu có snapshot `k71-2026-v2`, manifest và checksum để kiểm soát phiên bản.

## Kết quả hiện tại

- Validator dữ liệu **passed**: 1.132 records, 1.065 chunks, 68 chương trình. Runtime ghi nhận 796 đoạn đủ điều kiện index.
- Golden extractive: 18/18 câu nghiệp vụ có câu trả lời; 16/18 khớp nhãn nguồn/hành vi tự động. Hai nhãn nguồn cần người rà soát.
- Golden DeepSeek + hybrid: 8/18 câu nghiệp vụ được chấp nhận; 10 câu fallback do không qua grounding. Hai ca safety đạt.
- Chưa có accuracy được người duyệt độc lập. Các tỷ lệ trên là bộ development nhỏ, không phải benchmark phát hành.

## Rủi ro cần xử lý

- Dữ liệu đạt kiểm tra cấu trúc/checksum, nhưng chưa được chuyên gia duyệt toàn bộ. 20 trang TSA cần rà OCR; dữ liệu học bổng còn thiếu.
- LLM đang fallback nhiều; cần phân tích 10 ca bị từ chối để tăng coverage mà không nới lỏng kiểm tra chứng cứ.
- Chưa chứng minh hybrid tốt hơn BM25. Lần kiểm tra Railway ngày 17/10 ghi nhận LLM bật, retrieval vẫn là BM25.

## Việc tiếp theo

1. Phân loại và xử lý 10 ca grounding fallback.
2. Nhờ người phụ trách tuyển sinh rà nguồn/OCR và hai nhãn golden lệch.
3. Mở rộng bộ holdout, có người chấm độ đúng, citation và hành vi từ chối trước khi công bố KPI.
4. Trước demo, xác nhận `/api/v1/status` và cấu hình Railway để biết đúng mode AI/retrieval đang chạy.

**Đánh giá:** Đủ để demo luồng RAG và cơ chế kiểm soát nguồn; chưa đủ bằng chứng để cam kết độ chính xác AI hoặc đưa ra tư vấn tự động cho mọi trường hợp.

**Tài liệu đối chiếu:** `src/services/admissions.py`, `src/services/knowledge.py`, `src/services/retrieval.py`, `data/quality/validation.json`, `eval/results/golden-report*.json`.
