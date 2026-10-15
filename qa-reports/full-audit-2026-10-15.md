# Báo cáo QA toàn diện — 2026-10-15

## 1. Tóm tắt phạm vi và kết quả

Đã kiểm tra trực tiếp website production ở chế độ chỉ đọc tại trang sinh viên, trang đăng nhập admin và trang hàng chờ cán bộ bằng Chrome desktop. Đã rà soát giao diện responsive ở các chiều rộng CSS 1440, 1024, 767/769 (mục tiêu 768), 390 và 360 px; kiểm tra mở/đóng hộp công cụ chương trình, tải trang, bộ lọc ticket và nút làm mới.

Kết quả: xác nhận một lỗi nội dung giao diện mức Thấp tại trang cán bộ: dòng trợ giúp nói dữ liệu tự cập nhật, trong khi dấu thời gian không đổi sau hơn 7 giây và trang chỉ cập nhật sau khi bấm “Làm mới”. Không ghi nhận lỗi JavaScript/console ở trang cán bộ trong lần quan sát này. Các luồng ghi dữ liệu, tài khoản sinh viên và dashboard admin không được xác minh vì chỉ có thể kiểm tra an toàn đến trước thao tác tạo/cập nhật dữ liệu hoặc cần quyền phù hợp.

## 2. Môi trường kiểm thử

- Repository: `E:\AI1\P-051`; nhánh `main`, trạng thái ban đầu `main...team/main [ahead 2]`.
- Working tree ban đầu có thay đổi sẵn `M tests/conftest.py`; không sửa hoặc hoàn nguyên thay đổi này. Không tìm thấy `AGENTS.md` trong repository. Đã tham khảo hướng dẫn dự án và báo cáo QA vòng trước.
- Website production: Railway, trình duyệt Chrome desktop qua CUA. Phiên bản Chrome không được công cụ hiển thị. Không dùng tài khoản hoặc mật khẩu trong báo cáo.
- Thiết bị giả lập: devicePixelRatio 1.1. Chiều rộng CSS thực tế: 1440, 1024, 767/769, 390 và 360 px; chiều cao xấp xỉ lần lượt 900, 769, 1024, 844, 800 px. Công cụ viewport không thể đặt chính xác 768 CSS px (nhảy giữa 767 và 769), và một số chiều cao lệch 1 px.
- Không chỉnh sửa mã nguồn/dữ liệu dự án, không chạy migration, không deploy/push/commit. Không gửi email hay thao tác tạo tài khoản.

## 3. Các phần đã kiểm tra, không phát hiện lỗi

- **Trang sinh viên `/`**: tải trang và quan sát các vùng tra cứu, 68 chương trình, FAQ, nguồn/PDF, gợi ý ngành, checklist và ô nhập câu hỏi. Không gửi câu hỏi, không chuyển cán bộ, không mở PDF ngoài.
- **Responsive trang sinh viên**: các viewport đã nêu không có tràn ngang tài liệu quan sát được; thanh nhập câu hỏi vẫn hiện ở cạnh dưới. Hộp công cụ chương trình mở được và nút đóng hoạt động ở tablet/mobile được kiểm tra. Không tái hiện lỗi chồng nút hoặc phóng to trang như ảnh tham khảo trong lần kiểm tra này.
- **Trang cán bộ `/staff`**: phiên demo cán bộ có dữ liệu mẫu. Bộ lọc “Tất cả” hiển thị ba ticket mẫu và chi tiết ticket; bộ lọc mặc định “Đang chờ” hiện trạng thái rỗng phù hợp với số lượng 0. Nút “Làm mới” tải lại danh sách và cập nhật mốc thời gian. Không phát hiện lỗi console/error hoặc warning trong log trình duyệt được truy vấn.
- **Responsive quan sát trên giao diện**: không thấy thanh cuộn ngang tại các độ rộng mục tiêu. Với 390 px, `body` báo rộng xấp xỉ 391 px do làm tròn fractional pixel nhưng chiều rộng tài liệu là 390 px và không thấy tràn nội dung.
- **Trang `/admin`**: trang đăng nhập hiển thị và có nút vào demo admin không cần đăng nhập cùng thông tin demo. Không bấm nút vì có thể tạo phiên demo và vượt quá giới hạn chỉ đọc.

## 4. Lỗi

### BUG-001 — Hướng dẫn hàng chờ cán bộ nói dữ liệu tự cập nhật dù trang yêu cầu làm mới thủ công

- **Mức độ:** Thấp
- **Trạng thái:** Đã xác nhận
- **Nền tảng/trình duyệt/viewport:** Website production; Chrome desktop qua CUA; 1440 CSS px, DPR 1.1.
- **Route/chức năng:** `/staff`, danh sách ticket.
- **Điều kiện tiền đề:** Có phiên demo cán bộ hợp lệ; mở trang hàng chờ.
- **Bước tái hiện:**
  1. Mở `/staff` và đợi dữ liệu tải xong.
  2. Ghi nhận dòng “Kết quả được cập nhật tự động mà không xóa từ khóa hiện tại.” và mốc “Cập nhật lúc …”.
  3. Chờ hơn 7 giây mà không thao tác.
  4. Quan sát mốc thời gian không đổi. Bấm “Làm mới”; mốc thời gian thay đổi sau khi tải xong.
- **Thực tế:** Dòng trợ giúp khẳng định dữ liệu tự cập nhật, nhưng không thấy mốc tải/danh sách thay đổi sau hơn 7 giây. Làm mới thủ công cập nhật thời gian và dữ liệu.
- **Mong đợi:** Nội dung hướng dẫn nhất quán với hành vi hiện tại, nói rõ cần bấm “Làm mới” để tải lại.
- **Tần suất:** Tái hiện 1/1 lần quan sát; chờ trên 7 giây và đối chiếu trước/sau khi làm mới.
- **Bằng chứng:** Accessibility tree và nội dung DOM của trang có dòng hướng dẫn trên; dấu thời gian giữ nguyên qua khoảng chờ 7 giây, sau đó thay đổi sau khi bấm nút. Console không có lỗi/warning ở truy vấn này.
- **Ảnh hưởng:** Cán bộ có thể chờ cập nhật tự động và tưởng dữ liệu mới chưa đến, trong khi cần tự làm mới.
- **Gợi ý xử lý:** Sửa dòng trợ giúp để chỉ dẫn làm mới thủ công hoặc khôi phục cơ chế tự cập nhật nếu đó là hành vi dự kiến.

## 5. Phần bị chặn, giới hạn và giả định

- **Sinh viên — BLOCKED một phần:** Có thể quan sát trang tra cứu và giao diện nhập câu hỏi, nhưng không có tài khoản sinh viên an toàn được cấp cho kiểm thử. Không gửi câu hỏi/chuyển cán bộ vì tạo dữ liệu thật trên production. Chưa xác minh tra cứu có kết quả, chatbot, nguồn trích dẫn/PDF mở thành công, tìm kiếm/lọc có dữ liệu, xem lịch sử/phản hồi, phân quyền xem ticket và xác minh email.
- **Cán bộ — BLOCKED một phần:** Đã dùng phiên demo sẵn có để xem ticket mẫu, lọc “Tất cả” và làm mới. Không gửi phản hồi, từ chối, đóng hoặc đổi trạng thái vì các thao tác ghi dữ liệu. Chưa kiểm tra phân quyền giữa các cán bộ, tìm kiếm với nhiều truy vấn, lỗi API, phản hồi trùng hay gửi email.
- **Admin — BLOCKED:** Chỉ kiểm tra được màn hình đăng nhập. Không có phiên admin đã xác thực được cấp. Không bấm “Vào demo admin” vì tạo phiên có thể ghi trạng thái demo; không thử thông tin đăng nhập suy đoán. Dashboard, danh sách, bộ lọc và thao tác quản trị chưa được kiểm tra.
- **Kỹ thuật/network:** Có truy vấn log console của trang cán bộ nhưng không thu được console error/warning. Chưa kiểm tra trực tiếp toàn bộ Network/API, độ trễ, mã phản hồi hay lỗi tài nguyên cho mọi route. Không chạy test suite do môi trường thử nghiệm local an toàn không khởi chạy được trong lượt này.
- **Responsive:** Đã kiểm tra trực quan ở các kích thước gần mục tiêu; 768 px chính xác không thể đặt do giới hạn ánh xạ viewport của trình duyệt. Chưa xác minh trên thiết bị iOS/Android vật lý hoặc trình duyệt di động thực.
- **Side effect cần ghi nhận:** Khi mở trang sinh viên production, ứng dụng tự gọi luồng `/session` lúc khởi tạo. Vì vậy có khả năng ứng dụng đã tạo một phiên khách ẩn danh. Không gửi tin nhắn, không tạo ticket, không gửi email và không cố xóa phiên đó. Sau khi nhận ra hành vi khởi tạo phiên, đã dừng các tương tác sâu trên trang sinh viên production.
- **Giả định an toàn:** Ticket quan sát ở phiên cán bộ là dữ liệu demo dựa theo nhãn và nội dung mẫu của ứng dụng; không đưa mã ticket hoặc dữ liệu cá nhân vào báo cáo.

## 6. Thao tác đã dừng trước bước xác nhận

- Không gửi câu hỏi hoặc xác nhận chuyển câu hỏi cho cán bộ.
- Không gửi phản hồi, từ chối, đóng ticket hoặc thay đổi trạng thái.
- Không bấm nút vào demo admin, không đăng nhập bằng thông tin đoán.
- Không tạo tài khoản, sửa/xóa dữ liệu, gửi email, xác nhận thanh toán hoặc thực hiện thao tác không thể hoàn tác.
- Chỉ dùng thao tác GET/hiển thị: tải trang, xem ticket mẫu, chọn bộ lọc và bấm “Làm mới”.

## 7. Kết luận về mức độ sẵn sàng phát hành

Chưa đủ bằng chứng để kết luận toàn website sẵn sàng phát hành: còn một lỗi giao diện hướng dẫn đã xác nhận và các luồng cốt lõi có ghi dữ liệu, phân quyền sinh viên/cán bộ/admin, gửi email và phản hồi chưa được kiểm thử an toàn trên môi trường tách biệt. Responsive không cho thấy lỗi chồng nút/phóng to ở các viewport đã thử, nhưng chưa xác minh trên thiết bị di động thật. Nên xử lý nội dung BUG-001 và chạy lại các luồng bị chặn trên staging với dữ liệu giả, tài khoản kiểm thử và mail catcher trước khi đánh giá phát hành.

**Xác nhận:** Không gửi email thật, không cố ý thay đổi dữ liệu nghiệp vụ production, không deploy, push hoặc commit. Có khả năng một phiên khách ẩn danh được tạo tự động khi trang sinh viên production tải như đã nêu ở mục 5.
