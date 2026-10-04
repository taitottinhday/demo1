# Trợ lý tuyển sinh X
**Gate G1 — Brief | EDU-12 · Khối C (AI Vận hành) | Nhóm 1009 | Mã đội T051**

Phiên bản 1.1 · Cập nhật 04/10/2026 · Hạn G1: 20/09/2026, 23:59 (giờ Việt Nam). Trạng thái: đề xuất chốt thiết kế, chưa xác nhận pass.

## Bài toán và người dùng
Phòng tuyển sinh Trường đại học X nhận nhiều câu hỏi lặp về ngành học, quy trình, học phí và học bổng trên nhiều kênh. Cán bộ quá tải; ứng viên chờ lâu, thiếu hướng dẫn và có thể bỏ cuộc. Người dùng chính là ứng viên tìm hiểu hoặc chuẩn bị nộp hồ sơ; người dùng thứ hai là cán bộ tuyển sinh tiếp nhận các tình huống cần con người xử lý. Đây là mô tả bài toán được giao, chưa phải kết quả khảo sát của nhóm.

## Giải pháp
Web app với trợ lý AI tư vấn 24/7, tra cứu tài liệu tuyển sinh chính thức bằng RAG và trả lời có trích nguồn. Trợ lý hỗ trợ hội thoại nhiều lượt, hỏi thêm ngành/bậc học quan tâm khi cần, hướng dẫn bước tiếp theo và chuyển cán bộ khi thiếu căn cứ, vượt phạm vi hoặc có nội dung nhạy cảm. Không tự quyết định trúng tuyển, hứa học bổng hay suy diễn học phí, điều kiện và hạn nộp.

## Phạm vi MVP
1. **Ứng viên:** hỏi đáp, xem nguồn và checklist nộp hồ sơ lấy từ tài liệu đã xác minh; ngữ cảnh chỉ giữ trong phiên mặc định.
2. **AI có kiểm soát:** phát hiện ý định, truy xuất + rerank, kiểm tra căn cứ; hỏi làm rõ hoặc từ chối kết luận và đề nghị handover khi cần.
3. **Cán bộ:** đăng nhập, xem hàng chờ handover, nhận xử lý, phản hồi và đóng yêu cầu; ứng viên xem trạng thái bằng mã phiên/yêu cầu.
4. **Đánh giá:** bộ câu hỏi có nhãn và báo cáo answer rate, accuracy, lỗi nghiêm trọng, chi phí và độ trễ.

Nâng cao sau MVP: hồ sơ tự nguyện, nurture có đồng ý, dashboard engagement và caching có kiểm soát phiên bản nguồn. Ngoài phạm vi: nhận hồ sơ chính thức, thanh toán, quyết định tuyển sinh và tích hợp đa kênh ngay ở G1.

## Mục tiêu và cách kiểm chứng
**Answer rate ≥70%** = số tác vụ AI trả lời thực chất / toàn bộ tác vụ hỏi đáp tuyển sinh hợp lệ; **accuracy ≥85%** = số trả lời đúng, đủ, có căn cứ / số AI đã trả lời. Test tối thiểu 100 tác vụ có nhãn và 30 ca an toàn riêng; không chấp nhận bịa nghiêm trọng. **Giảm ≥50% tải câu hỏi cho cán bộ** qua baseline/pilot tương đương, tính cả handover và kênh khác trên 100 ứng viên. Đây là mục tiêu chưa có số đo đạt; PRD quy định phép đo và nghiệm thu.

## Thiết kế và điều kiện triển khai
Next.js chat widget → FastAPI → điều phối intent → RAG PostgreSQL/pgvector + reranker → LLM + kiểm tra căn cứ; LangGraph là lựa chọn đề xuất. Docker/cloud khi triển khai. Nguồn có URL, phiên bản, kỳ và hiệu lực, người duyệt; nguồn thu hồi không được trả lời mới. Cần chốt trường X, cán bộ HITL, nguồn, ngân sách và dữ liệu pilot. Chỉ thu dữ liệu tối thiểu; hỏi đáp không yêu cầu định danh. Mục tiêu p95 ≤10 giây ở 20 phiên đồng thời; timeout và hạn mức chi phí có fallback.

## Thành viên
| Họ tên | Mã học viên |
|---|---|
| Nguyễn Quang Huy | 2A202602820 |
| Lê Văn Tài | 2A202602464 |
| Cao Văn Cường | 2A202602493 |
| Chu Phúc Anh | 2A202602370 |

**Bàn giao G1:** [PRD](prd.md), [wireframe](wireframe/index.html), [UI flow](wireframe/ui-flow.md); bản in một trang: [brief.html](brief.html). Nhóm/người duyệt cần xác nhận phạm vi và phụ thuộc trước MVP; thông tin thành viên kế thừa từ hồ sơ hiện có. Chưa có bằng chứng triển khai hay KPI đạt.
