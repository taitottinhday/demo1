# Báo cáo kiểm thử vòng 2 — Trợ lý tuyển sinh X

**Ngày:** 10/10/2026 (Asia/Ho_Chi_Minh)

**Production:** https://demo1-production-f54e.up.railway.app/

**Mốc mã được kiểm tra cục bộ:** `783acec` (`Fix quota answer routing for AI mode`)
**Build dữ liệu trên production:** `6991e9023c3e…`; giao diện hiển thị 68 chương trình, 8 nguồn và 5 PDF tra cứu.

## Kết luận

**NO-GO cho phát hành dựa trên bằng chứng hiện có.** Không phát hiện lỗi mới nghiêm trọng trên các luồng đã xem; tuy nhiên bộ kiểm thử đầy đủ vẫn đỏ (94 pass, 1 fail), còn lỗi lint, độ phủ AI production thấp, và chưa xác minh được phản hồi trong đúng phiên thí sinh sở hữu ticket. Đây là kết luận về mức độ sẵn sàng kiểm thử, không phải kết luận rằng production hiện đang hỏng.

Không sửa mã sản phẩm hoặc dữ liệu tuyển sinh trong vòng audit này. Một ticket QA_TEST production đã được người dùng cho phép xử lý: nhận ticket một lần, gửi một phản hồi có căn cứ từ tài liệu 2026, rồi đóng ticket. Không thao tác ticket production nào khác.

## Ma trận kiểm thử

`ROUND2_TEST_CASES.csv` có 52 trường hợp: **26 PASS, 3 PARTIAL, 1 BLOCKED, 2 FAIL, 20 NOT_TESTED**. Hai FAIL là một test trong full suite và một kiểm tra lint; chúng không phải lỗi production đã xác nhận. BLOCKED là kiểm tra trực tiếp HTTP/network/latency do công cụ trình duyệt không cung cấp số liệu request. Ba PARTIAL gồm kiểm tra giao diện tablet, xác minh lịch sử trùng ban đầu trong đúng session cũ, và hiển thị ticket ở phiên thí sinh sở hữu.

`ROUND2_AI_ACCURACY.csv` gồm 150 câu hỏi có ground truth/source: **4 câu chạy cục bộ**, **1 câu trả lời AI trên ticket production có sẵn được đối chiếu**, **145 câu chưa chạy**. Không tính phần trăm accuracy tổng thể từ 5 mẫu này. Bộ 20 kịch bản hội thoại nhiều lượt trong ma trận chức năng đều chưa chạy trên production.

## Những điểm đã xác minh

- Câu hỏi IT1/IT2 về quota trong các test cục bộ trả đúng dữ liệu trích xuất; ticket production IT2 được mở lại ở cán bộ/admin có chỉ tiêu **200**, nguồn PDF trang 10.
- CTA checklist hiện mô tả đúng hành động: xem PDF trang 18, mở cổng TSA và mở cổng đăng ký nguyện vọng; liên kết ngoài mở tab mới với `rel=noopener`.
- So sánh IT1/IT2 giữ số liệu riêng theo chương trình, kèm nguồn; phần gợi ý ngành giải thích theo dữ liệu người nhập, nêu rõ tiêu chí thiếu dữ liệu và không dựng phần trăm phù hợp.
- Trang admin không còn thẻ “tỷ lệ chuyển cán bộ” vượt 100%; chỉ số liên quan hiển thị số yêu cầu, các tỷ lệ còn lại có công thức, tử/mẫu và múi giờ.
- Cán bộ nhận ticket QA_TEST, gửi phản hồi đúng nội dung nguồn, và trạng thái “Đã giải quyết” cùng lịch sử thao tác được xác nhận lại trên admin.
- Các phiên thí sinh hiện có không sở hữu ticket QA_TEST này và vẫn hiển thị empty state. Vì vậy, chưa xác minh được người thí sinh sở hữu ticket nhìn thấy phản hồi.
- Không có lỗi/warning console trong các trang được lấy log ở lần kiểm tra này.

## Hạng mục cần xử lý trước khi công bố rộng

1. Điều tra/cập nhật `test_llm_quote_validation_and_failure`: test hiện yêu cầu đi qua nhánh LLM trong khi câu hỏi quota đang được xử lý bằng nhánh trích xuất xác định; quyết định test hay hành vi nào là hợp đồng đúng rồi sửa đồng bộ.
2. Sửa 3 lỗi `ruff check src tests` (2 lỗi trong `src/services/knowledge.py`, 1 lỗi trong test nguồn dữ liệu).
3. Xác minh bằng fixture/session cô lập rằng phản hồi ticket nhìn thấy ở đúng phiên thí sinh sở hữu.
4. Chạy đủ 150 câu và 20 luồng hội thoại dài trên môi trường staging có kiểm soát, không bắn benchmark lên production.
5. Bổ sung kiểm thử bảo mật API và đo network/latency bằng công cụ có quyền xem request.

Chi tiết nằm trong các báo cáo cùng thư mục, đặc biệt [ROUND2_RISK_ASSESSMENT.md](ROUND2_RISK_ASSESSMENT.md), [ROUND2_E2E_REPORT.md](ROUND2_E2E_REPORT.md) và [ROUND2_AI_EVALUATION.md](ROUND2_AI_EVALUATION.md).
