# Trợ lý tuyển sinh X — MVP HUST 2026

Web app demo hai vai trò: ứng viên hỏi đáp có trích nguồn và cán bộ xử lý handover. Nguồn là PDF tuyển sinh HUST 2026 **51 trang** do nhóm cung cấp; chưa được cán bộ tuyển sinh duyệt. Giao diện chạy cùng FastAPI, không cần Node.js.

Phòng tuyển sinh phải xử lý nhiều câu hỏi lặp; ứng viên cần tra cứu nhanh và chuyển người phụ trách khi thiếu căn cứ. MVP cung cấp hỏi đáp từ tài liệu, so sánh 2–3 chương trình, đánh giá câu trả lời và handover có sự đồng ý. Cán bộ nhận, phản hồi hoặc từ chối có lý do; ứng viên được hủy yêu cầu còn mở và nhận dấu báo phản hồi mới.

Stack triển khai: FastAPI + HTML/CSS/JavaScript, SQLite, PyMuPDF, BM25 với quy tắc ưu tiên theo ý định, OpenAI tùy chọn. Các phiên bản thư viện trực tiếp được cố định theo môi trường đã chạy kiểm thử; `requirements.txt` chưa là lockfile toàn bộ thư viện phụ thuộc.

## Chạy ngay trên Windows

Mở PowerShell trong `C:\Users\Huy\P-051`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_mvp.ps1
```

Máy mới hoặc cần cài lại thư viện:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_mvp.ps1 -Install
```

Mở **http://127.0.0.1:8000/** cho ứng viên và **http://127.0.0.1:8000/staff** cho cán bộ. Local demo mặc định: tài khoản `canbo`, mật khẩu `Demo@2026!` (trừ khi bạn đã đổi trong `.env`). Dừng server bằng `Ctrl+C`. Nếu cổng 8000 đang dùng, thêm `-Port 8001`.

Script tạo `.venv` nếu thiếu, giữ nguyên `.env` hiện có và tự lập chỉ mục PDF khi khởi động. `data/sources.md` phải trỏ đúng file `raw/thong-tin-tuyen-sinh-dai-hoc-2026f.pdf`. Không mở trực tiếp file HTML bằng `file://`; UI cần server để gọi API.

Sau khi sửa Python hoặc cấu hình `.env`, dừng và chạy lại server để nạp code mới và bỏ cache cũ; tải lại trang không khởi động lại backend. Sau khi sửa giao diện, dùng Ctrl+F5.

## Chế độ demo và AI

| Biến môi trường MVP | Mặc định / ý nghĩa |
|---|---|
| `ANSWER_MODE` | `extractive`; `llm` cần API key |
| `OPENAI_API_KEY`, `MODEL_NAME` | Chỉ dùng khi bật LLM; không đưa key vào Git |
| `STAFF_USERNAME`, `STAFF_PASSWORD` | Tài khoản demo; đổi mật khẩu trước khi public |
| `MVP_DATA_DIR` | `data`; thư mục nguồn và SQLite |
| `SESSION_HOURS` | `24`; thời gian phiên ứng viên không hoạt động |
| `SECURE_COOKIES` | `false` cho local HTTP; `true` cho HTTPS production |
| `LLM_DAILY_LIMIT`, `LLM_TIMEOUT` | `100` lượt/ngày và `15` giây |
| `APP_ENV` | `development`; production kiểm tra mật khẩu và cookie |

Mặc định `ANSWER_MODE=extractive`: tra cứu đoạn tài liệu thật, có trang nguồn, không gọi LLM và không cần API key. Để bật AI tổng hợp, bổ sung/chỉnh các dòng trong `.env`, rồi khởi động lại:

```dotenv
ANSWER_MODE=llm
OPENAI_API_KEY=your-real-key
MODEL_NAME=gpt-4o-mini
LLM_DAILY_LIMIT=100
LLM_TIMEOUT=15
```

Không gửi key trong chat hoặc commit `.env`. Chế độ LLM dùng Responses API và đầu ra có schema theo [official OpenAI documentation](https://developers.openai.com/api/docs/guides/structured-outputs). Quote và dữ kiện số được kiểm tra trước hiển thị; thiếu nguồn/lỗi model/hết hạn mức chuyển fallback. Hạn mức theo số lượt gọi, chưa phải trần tiền. Cấu hình placeholder hiện có sẽ không chạy AI; chế độ tra cứu vẫn demo được.

## Demo theo trình tự

1. Hỏi **“IT1 có chỉ tiêu bao nhiêu?”** → 300, trang PDF 10; mở nguồn.
2. Hỏi tiếp **“Học phí bao nhiêu?”** → dự kiến 28–40 triệu đồng/năm học cho chương trình chuẩn, trang PDF 20.
3. Mở **Checklist đăng ký ĐGTD**, đối chiếu nguồn và link chính thức.
4. Hỏi **“Tôi có chắc chắn trúng tuyển không?”** → không cam kết, đề nghị cán bộ.
5. Chuyển cán bộ → sửa nội dung → đồng ý → gửi. Mở `/staff`, đăng nhập → nhận xử lý → phản hồi và đóng.
6. Quay về ứng viên → **Yêu cầu của tôi → Làm mới** để xem phản hồi. Tải lại trang để kiểm tra dữ liệu còn được lưu.

G1 vẫn là hồ sơ thiết kế; bản demo dùng SQLite/BM25 và giao diện web trực tiếp thay cho Next.js/pgvector đề xuất. Code LangGraph mẫu không được gọi trong luồng chat.

## Hồ sơ Gate 2

| Deliverable | Vị trí / trách nhiệm |
|---|---|
| Video 3 phút end-to-end | Nhóm quay: hỏi đáp có nguồn → thiếu nguồn → đồng ý handover → cán bộ phản hồi → ứng viên đọc |
| Components và data flow | [Sơ đồ kiến trúc](docs/architecture_diagram.md) |
| ≥10 PR merged | Nhóm cung cấp link PR đã merged |
| Setup, env vars, sample queries | README này |
| ≥5 ca manual với output thực tế | [Evidence](eval/manual-tests.md); cần người kiểm tra xác nhận manual |

Nguồn chưa được cán bộ HUST duyệt; app là demo của nhóm. Chỉ dùng phạm vi tuyển sinh chính quy từ THPT. Bảng quy đổi chứng chỉ trang 17 dạng ảnh chưa được xác minh; học bổng, hướng dẫn KTX và chuẩn ngoại ngữ đầu ra chưa đủ nguồn.

Phiên ứng viên hết hạn sau 24 giờ không hoạt động; phiên cán bộ 8 giờ. Xóa chat không xóa ticket. Ticket được dọn sau 30 ngày không cập nhật, chỉ phù hợp demo. Dấu phản hồi đã xem lưu trên trình duyệt; thông báo mới chỉ hoạt động khi mở app, không gửi email hoặc push.

## Cấu trúc và phân công

| Vai trò | Phạm vi |
|---|---|
| Frontend | `src/web/`, kiểm thử luồng tại `scripts/check_browser.py` |
| Backend | `src/api/routes.py`, `src/services/store.py`, phiên, quyền và API |
| Data + AI | `knowledge.py`, `admissions.py`, `answer_formatter.py`, `product_features.py`, ingest và eval |
| Tích hợp | `src/main.py`, `src/config.py`, dependencies, CI và Docker |

Swagger API tại `/docs`; kiến trúc thực tế tại [architecture_diagram.md](docs/architecture_diagram.md). `src/agents/` và `src/services/llm.py` là mẫu kế thừa, không nằm trong luồng chat MVP. Danh sách thành viên và công việc thực tế cần cập nhật trong `WORKLOG.md`, `JOURNAL.md`; không dùng nội dung template làm bằng chứng công việc.

AI usage logging kế thừa: chạy `scripts/setup_hooks.ps1` một lần sau clone nếu khóa học yêu cầu. `AI_LOG_API_KEY` là key cá nhân, không commit. Hướng dẫn chung ở `docs/guide/`, tiêu chí nộp của Gate 2 cần đối chiếu riêng với mentor.

## Kiểm thử và đánh giá

Evidence Gate 2: [6 ca với output thực tế](eval/manual-tests.md). Người kiểm tra điền kết luận manual sau khi lặp lại trên UI và đối chiếu nguồn. Sơ đồ components/data flow: [Architecture diagram](docs/architecture_diagram.md). Video 3 phút và ≥10 PR merged do nhóm chuẩn bị.

```powershell
New-Item -ItemType Directory -Force data/test-tmp | Out-Null
.venv/Scripts/python.exe -m pytest -q --basetemp=data/test-tmp/local-check
.venv/Scripts/python.exe -m ruff check src tests scripts/ingest_sources.py scripts/evaluate_mvp.py scripts/check_browser.py
.venv/Scripts/python.exe -X utf8 -m scripts.evaluate_mvp
```

`--basetemp` phải là thư mục chỉ dành cho test vì pytest sẽ dọn nội dung của nó. Báo cáo tại [eval/results/report.md](eval/results/report.md) và `mvp-report.json`. Bộ 40 ca dự thảo là regression development; đối chiếu từ khóa/trang không thay thế accuracy được cán bộ duyệt. Cần bộ holdout 100 hỏi đáp + 30 an toàn và pilot trước khi công bố đạt KPI đề tài.

Kiểm thử browser tùy chọn (không cần để chạy app): cài `playwright`, chạy server, rồi dùng `python -m scripts.check_browser --browser "C:/Program Files/Google/Chrome/Application/chrome.exe"`. Script dùng hồ sơ trình duyệt tạm, tạo ticket DEMO UI và lưu ảnh tại `data/processed/demo/`.

## Docker và máy khác

```powershell
docker compose up --build
```

Mở cùng các URL ở trên. `data/sources.md` và PDF công khai được phép đưa vào Git để clone repo có thể chạy lại; database, dữ liệu xử lý và dữ liệu ứng viên vẫn bị ignore. SQLite nằm tại `data/mvp.db`, không đưa dữ liệu ứng viên hoặc `.env` vào Git. Hiện chỉ xác minh chạy local; chưa deploy cloud. Public deployment cần HTTPS, đổi mật khẩu riêng ≥12 ký tự, `SECURE_COOKIES=true`, `APP_ENV=production` và nguồn được duyệt; production sẽ từ chối mật khẩu demo.

Nếu nguồn chưa sẵn sàng: kiểm tra `/api/v1/status`, đường dẫn PDF và `sources.md`, rồi khởi động lại. PDF scan cần OCR/duyệt trước lập chỉ mục. Nếu AI lỗi: kiểm tra cấu hình/quota API, hoặc đổi `ANSWER_MODE=extractive`. Nếu đăng nhập lỗi sau deploy HTTPS: kiểm tra cookie Secure và origin.

