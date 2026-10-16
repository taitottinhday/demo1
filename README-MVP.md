# Trợ lý tuyển sinh X — tích hợp Data + AI HUST 2026

Tên file được giữ để các liên kết hiện có tiếp tục hoạt động. Phần Data + AI
đang được hoàn thiện cho project tích hợp: DeepSeek, nguồn tuyển sinh có phiên
bản, PostgreSQL + pgvector, BM25 và reranker. Các mục mô tả demo bên dưới ghi
lại nền ứng dụng hiện có; không phải kết luận hệ thống đã đủ điều kiện vận hành
chính thức. Nghiệm thu AI cần tập đánh giá độc lập và cán bộ duyệt nội dung.

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
| `LLM_PROVIDER` | `openai` hoặc `deepseek`; `.env.example` đề xuất DeepSeek |
| `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL` | Key ở server; model mặc định `deepseek-flash` |
| `LLM_MAX_OUTPUT_TOKENS` | `1200`; giới hạn output mỗi lượt (128–2000) |
| `OPENAI_API_KEY`, `MODEL_NAME` | Chỉ dùng khi bật LLM; không đưa key vào Git |
| `STAFF_USERNAME`, `STAFF_PASSWORD` | Tài khoản demo; đổi mật khẩu trước khi public |
| `MVP_DATA_DIR` | `data`; thư mục nguồn tuyển sinh và dữ liệu xử lý knowledge |
| `PERSISTENT_DATA_DIR` | Trống khi local; production phải trỏ tới Railway Volume, ví dụ `/app/state`, để giữ tài khoản, ticket, session và lịch sử |
| `SESSION_HOURS` | `24`; thời gian phiên ứng viên không hoạt động |
| `SECURE_COOKIES` | `false` cho local HTTP; `true` cho HTTPS production |
| `LLM_DAILY_LIMIT`, `LLM_TIMEOUT` | `100` lượt/ngày và `15` giây |
| `APP_ENV` | `development`; production kiểm tra mật khẩu và cookie |

Các trang cán bộ và admin có nút **Vào thử** trong môi trường `development`/`test`; nút tạo phiên demo để mentor thực hành. API demo trả 404 trong `production`, nơi vẫn yêu cầu đăng nhập tài khoản được cấp.

### Email thông báo phản hồi

Ứng dụng dùng chung nhà cung cấp email đang có: ưu tiên Resend HTTPS (`RESEND_API_KEY`, `RESEND_FROM`), sau đó dùng SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_SECURITY`). `PUBLIC_BASE_URL` phải là URL gốc người dùng có thể truy cập; production cần HTTPS. Không commit `.env` hoặc bí mật nhà cung cấp.

Sau khi phản hồi được lưu, tác vụ nền gửi email ngắn đến email hợp lệ đã xác minh của tài khoản sinh viên liên kết với ticket. Email chỉ có mã ticket và đường dẫn đăng nhập; nội dung trao đổi không được đưa vào thư. Cán bộ xem trạng thái gửi tại chi tiết ticket và có thể gửi lại nếu thất bại. Khi không cấu hình provider ở local, phản hồi vẫn được lưu và trạng thái email báo thất bại; test dùng mailer giả, không gửi email thật. Tác vụ nền hiện dùng FastAPI `BackgroundTasks`, chưa có hàng đợi bền vững; nếu tiến trình dừng đột ngột trong lúc gửi, cần kiểm tra trạng thái vận hành trước khi thử lại.

Mặc định `ANSWER_MODE=extractive`: tra cứu đoạn tài liệu thật, có trang nguồn, không gọi LLM và không cần API key. Để bật AI tổng hợp, bổ sung/chỉnh các dòng trong `.env`, rồi khởi động lại:

```dotenv
ANSWER_MODE=llm
OPENAI_API_KEY=your-real-key
MODEL_NAME=gpt-4o-mini
LLM_DAILY_LIMIT=100
LLM_TIMEOUT=15
```

Không gửi key trong chat hoặc commit `.env`. Chế độ LLM dùng Responses API và đầu ra có schema theo [official OpenAI documentation](https://developers.openai.com/api/docs/guides/structured-outputs). Quote và dữ kiện số được kiểm tra trước hiển thị; thiếu nguồn/lỗi model/hết hạn mức chuyển fallback. Hạn mức theo số lượt gọi, chưa phải trần tiền. Cấu hình placeholder hiện có sẽ không chạy AI; chế độ tra cứu vẫn demo được.

### DeepSeek

Để thử DeepSeek, tự nhập key vào `.env` rồi khởi động lại server:

```dotenv
ANSWER_MODE=llm
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-real-key
DEEPSEEK_MODEL=deepseek-flash
LLM_DAILY_LIMIT=20
LLM_MAX_OUTPUT_TOKENS=1200
LLM_TIMEOUT=15
```

Adapter DeepSeek dùng Chat Completions + JSON Output, validate cấu trúc tại server rồi kiểm tra quote/số liệu trước hiển thị. Output rỗng, bị cắt, sai schema hoặc thiếu căn cứ chuyển fallback; lỗi provider/timeout trả thông báo lỗi có đường chuyển cán bộ. Không retry ngầm; giới hạn 24.000 ký tự câu hỏi + nguồn trước khi gọi. Các giới hạn này chưa thay thế trần chi phí tiền tệ hoặc benchmark tải. Câu chỉ tiêu vẫn dùng trích xuất xác định và không gọi model. Tham khảo [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/).

Kiểm thử tự động provider dùng mock; smoke-test live được ghi riêng bên dưới. Embedding/pgvector/reranker chưa được tích hợp. Corpus chuẩn hóa hiện thay phần trích trang PDF bổ trợ, có kiểm tra checksum và lọc quality/scope; bảng chương trình/học phí nguồn chính giữ parser hiện tại. API/citation và giao diện không thay đổi.

Cập nhật 16/10/2026: đã smoke-test live model `deepseek-flash`: request kết nối 42 token; một câu giới thiệu IT1 qua retrieval/grounding dùng 646 token, khoảng 2 giây cho bước trả lời, citation PDF trang 10. Đây chỉ là kiểm tra kết nối và một câu trả lời, không phải benchmark KPI. Một lần thử trong sandbox bị chặn mạng và không có response từ provider.

Đánh giá local không tốn API bằng bộ golden 20 ca:

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.evaluate_mvp --suite golden --mode extractive
```

Kết quả trong `eval/results/golden-report.json`. Bộ này là development, không phải holdout. Chỉ số `automatic_behavior_source_match` kiểm tra kind và source ID kỳ vọng, không chấm tính đúng/đủ của claim. Hai ca còn lệch source kỳ vọng (phương thức toàn trường và học phí IT1 theo năm) cần người duyệt nhãn/phạm vi: nguồn khác không tự động có nghĩa câu trả lời sai. Chạy LLM eval phải chỉ định `--mode llm --max-calls N`; không có cờ giới hạn thì lệnh dừng trước khi gọi API. Tối đa N ca được đánh giá và vẫn chịu hạn mức LLM trong cấu hình.

## Demo theo trình tự

1. Hỏi **“IT1 có chỉ tiêu bao nhiêu?”** → 300, trang PDF 10; mở nguồn.
2. Hỏi tiếp **“Học phí bao nhiêu?”** → dự kiến 28–40 triệu đồng/năm học cho chương trình chuẩn, trang PDF 20.
3. Mở **Checklist đăng ký ĐGTD**, đối chiếu nguồn và link chính thức.
4. Hỏi **“Tôi có chắc chắn trúng tuyển không?”** → không cam kết, đề nghị cán bộ.
5. Chuyển cán bộ → sửa nội dung → đồng ý → gửi. Mở `/staff`, đăng nhập → nhận xử lý → phản hồi và đóng.
6. Quay về ứng viên → **Yêu cầu của tôi → Làm mới** để xem phản hồi. Tải lại trang để kiểm tra dữ liệu còn được lưu.

## Trang quản trị (Admin)

Mở **http://127.0.0.1:8000/admin**, đăng nhập `admin` / `Admin@2026!` (đổi bằng `ADMIN_USERNAME`, `ADMIN_PASSWORD` trong `.env`). Đặc tả đầy đủ ở `ADMIN_SPEC.md`.

- Tài khoản nằm trong bảng `users`. Khi server khởi động, `canbo` (role officer) và `admin` được tạo từ `.env` nếu chưa có. Đổi mật khẩu trong `.env` sau lần chạy đầu không cập nhật tài khoản đã có.
- `/staff/login` chỉ nhận officer đang hoạt động. `/admin/login` chỉ nhận admin. Hai loại cookie tách riêng.
- Chức năng: xem và lọc toàn bộ ticket, xem chi tiết kèm hội thoại, nguồn và lịch sử (`ticket_events`). Phân công lại hoặc trả về hàng chờ. Tạo, khóa hoặc mở cán bộ: khóa thì ticket họ đang giữ tự trả về hàng chờ. Có thêm metrics.
- `ADMIN_STALE_HOURS` (mặc định `24`) là ngưỡng hiển thị "ticket chờ quá lâu".
- Dữ liệu demo gồm 9 cán bộ demo (cùng tài khoản mặc định `canbo` là khoảng 10 cán bộ), mật khẩu demo `Demo@2026!`, và 50 ticket `TS-DEMO01` đến `TS-DEMO50` đủ trạng thái. Chạy được nhiều lần, không tạo trùng. Trong production chỉ chạy seed có chủ đích bằng `DEMO_SEED_ENABLED=true`:

```powershell
.\.venv\Scripts\python.exe scripts\seed_admin_demo.py
```

Kịch bản demo admin, khoảng 2 phút:

1. Tab **Ticket**, lọc "Đang chờ", mở `TS-DEMO01`: xem lý do chuyển, hội thoại và nguồn.
2. Tab **Tổng quan**: thời gian chờ trung bình, tải từng cán bộ, ticket chờ quá lâu.
3. Mở `TS-DEMO05`, phân công cho cán bộ khác, rồi xem sự kiện mới trong **Lịch sử**.
4. Tab **Cán bộ**: khóa Nguyễn Thị Lan. Hộp xác nhận nêu số ticket sẽ về hàng chờ.

Trên Railway, chạy seed sau khi đã gắn Volume `/app/state` và đặt `PERSISTENT_DATA_DIR=/app/state`:

```sh
DEMO_SEED_ENABLED=true DEMO_SEED_FAST=true python scripts/seed_admin_demo.py
```

`DEMO_SEED_FAST=true` chỉ dùng cho dữ liệu kiểm thử, không gọi pipeline trả lời; các ticket được gắn câu trả lời demo rõ ràng và không phải nội dung tuyển sinh chính thức.

Giới hạn hiện tại:

- `confidence_score` luôn `null`.
- `handover_rate` trả `null` cho đến khi bên AI ghi bảng `chat_logs`.
- Ticket tạo trước khi có phần admin không có lịch sử và mốc thời gian nhận.

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

Phiên ứng viên hết hạn sau 24 giờ không hoạt động; phiên cán bộ 8 giờ. Xóa chat không xóa ticket. Ticket được dọn sau 30 ngày không cập nhật, chỉ phù hợp demo. Trạng thái hàng chờ và phản hồi không tự tải lại định kỳ; dùng nút **Làm mới** ở trang cán bộ/admin hoặc trong cửa sổ yêu cầu của sinh viên.

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

Mở cùng các URL ở trên. `data/sources.md` và PDF công khai được phép đưa vào Git để clone repo có thể chạy lại; database, dữ liệu xử lý và dữ liệu ứng viên vẫn bị ignore. Ở local, Docker Compose lưu state tại `/app/state` và mount từ `data/state`. Trên Railway, tạo Volume mount tại `/app/state` và đặt `PERSISTENT_DATA_DIR=/app/state`; giữ `MVP_DATA_DIR=data` để Volume không che các PDF nguồn. Public deployment cần HTTPS, đổi mật khẩu riêng ≥12 ký tự, `SECURE_COOKIES=true`, `APP_ENV=production` và nguồn được duyệt; production sẽ từ chối mật khẩu demo. Hai nút demo ở trang cán bộ/admin dùng database mẫu riêng tại `PERSISTENT_DATA_DIR/demo/mvp.db`, không truy cập ticket/tài khoản thật và không gửi email.

Nếu nguồn chưa sẵn sàng: kiểm tra `/api/v1/status`, đường dẫn PDF và `sources.md`, rồi khởi động lại. PDF scan cần OCR/duyệt trước lập chỉ mục. Nếu AI lỗi: kiểm tra cấu hình/quota API, hoặc đổi `ANSWER_MODE=extractive`. Nếu đăng nhập lỗi sau deploy HTTPS: kiểm tra cookie Secure và origin.

## Railway persistence

The mutable SQLite state (staff accounts, candidate accounts, tickets, statuses, sessions and audit history) must live on a Railway Volume. Configure the service once:

1. Add a Railway Volume and mount it at `/app/state`.
2. Set `PERSISTENT_DATA_DIR=/app/state`.
3. Keep `MVP_DATA_DIR=data`; do not mount the Volume over `/app/data`, because that directory contains the bundled source PDF and `sources.md`.
4. With one replica, deploy and verify that a test ticket and its status still exist after a restart.

Production now refuses to start without `PERSISTENT_DATA_DIR` or when it points to the knowledge directory. This prevents a deploy from appearing healthy while silently creating a blank database. SQLite on a shared Volume is intended for one replica; use PostgreSQL before scaling horizontally.

## PostgreSQL + pgvector local cho RAG

Database RAG chạy riêng với SQLite của ứng dụng. Mở Docker Desktop, đặt
`RAG_POSTGRES_PASSWORD` và `RAG_DATABASE_URL` trong `.env` (xem `.env.example`), rồi chạy:

```powershell
docker compose -f docker-compose.rag.yml up -d --wait
docker compose -f docker-compose.rag.yml exec -T rag-db psql -U admissions_rag -d admissions_rag -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

PostgreSQL chỉ lắng nghe trên `127.0.0.1:55432`. Named volume `rag-postgres`
giữ dữ liệu qua các lần khởi động lại. Dừng bằng
`docker compose -f docker-compose.rag.yml down`; không thêm `-v` nếu muốn giữ dữ liệu.
Nếu backend cũng chạy trong Docker, URL kết nối cần dùng hostname của service trên
cùng Docker network thay cho `127.0.0.1`.
### Embedding, hybrid retrieval và reranker

Trong môi trường Python của project, cài thư viện RAG và tạo chỉ mục:

```powershell
python -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-rag.txt
python -m scripts.build_rag_index
```

Lần tạo đầu tải model công khai; không gọi DeepSeek, không tốn token LLM.
Model được cố định revision trong `src/services/retrieval.py`. Embedding dùng
`intfloat/multilingual-e5-small` (384 chiều, prefix query/passage), reranker dùng
`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`. Chất lượng tiếng Việt phải đo trên
bộ câu hỏi tuyển sinh; tên model đa ngôn ngữ không bảo đảm đạt KPI.

Sau khi build thành công, đặt `RETRIEVAL_MODE=hybrid` trong `.env` và khởi động
lại backend. Kiểm tra `knowledge.manifest.retrieval`: `hybrid` là sẵn sàng,
`bm25_fallback` là thiếu model/index hoặc database không sẵn sàng. Runtime chỉ
đọc model đã cache, không tự tải model khi có câu hỏi. Đổi nguồn hoặc revision
embedding cần chạy lại lệnh build; các snapshot cũ được giữ để hỗ trợ rollback.

Vector chỉ lập chỉ mục các chunk nguồn công khai đã qua bộ lọc của runtime,
không chứa hội thoại hay hồ sơ ứng viên. Dữ liệu dài được chia cửa sổ token có
chồng lấn khi embedding. Truy xuất kết hợp cosine và BM25 bằng RRF, rồi rerank
tối đa `RAG_CANDIDATES=8` ứng viên. Tìm kiếm cosine chính xác phù hợp corpus
hiện tại; chưa cần ANN. Các bộ lọc phạm vi và bằng chứng từ khóa được giữ;
hybrid hiện cải thiện thứ tự ứng viên, chưa mở rộng trả lời câu không có bằng
chứng từ khóa. Các nhánh dữ kiện học phí/điểm chuẩn/chương trình và điều kiện
ngoại ngữ vẫn giữ logic riêng. Reranker không thay thế kiểm chứng câu trả lời.

Build image có RAG bằng `docker build --build-arg WITH_RAG=true -t admissions-ai .`.
Mount thư mục model cache đã tạo hoặc chạy lệnh build index trong môi trường
container có volume cache ghi được. Không đưa model, mật khẩu hay database vào Git.

So sánh bằng bộ kiểm tra hiện có (không gọi API trả phí):

```powershell
python -m scripts.evaluate_mvp --suite golden --retrieval bm25
python -m scripts.evaluate_mvp --suite golden --retrieval hybrid
```

Báo cáo hybrid có hậu tố riêng và từ chối chạy nếu thực tế đang dùng fallback.
Đây là kiểm tra hành vi/nguồn trên tập phát triển, không phải accuracy được
cán bộ xác nhận và không đủ để kết luận đạt KPI nghiệm thu.

Kiểm tra local ban đầu ngày 16/10/2026: index có 513 chunk/530 cửa sổ. Với 8 ứng viên,
hai truy vấn smoke test trả đúng học bổng Trần Đại Nghĩa (trang 25–26) và bảo lưu
kết quả (trang 13 của quy chế); thời gian truy xuất lần lượt khoảng 354 ms và
1.241 ms trên máy phát triển. Đây không phải p95 hay kiểm thử mùa cao điểm.
Sau bổ sung bảng điểm 2026 chính thức đủ 68 chương trình và bốn cột phương thức,
index hiện có 1.047 chunk/1.068 cửa sổ, từ 9 nguồn: nạp đủ 796 đoạn native
đạt điều kiện thuộc đại học chính quy, tương ứng 789 bản ghi, không giới hạn
trang của tài liệu chính. Trong 1.065 đoạn snapshot, 193 đoạn cần duyệt nội dung
và 76 đoạn ngoài phạm vi đại học chính quy không được nạp. JSONL theo chủ đề là
view của records, không nạp trùng. Xem `source.normalized_coverage` tại
`/api/v1/status` để kiểm tra. Điểm chuẩn lịch sử chỉ được truy xuất theo đúng
năm và chương trình; citation giữ năm của bản ghi. Học bổng công khai được trả
lời từ chính sách, quyết định điều kiện cá nhân vẫn chuyển cán bộ.

Golden development: cả BM25 và hybrid đều khớp nhãn 18/20, an toàn 2/2,
0 token LLM. Hai lệch nguồn/nhãn ADM-001 và FEE-001 vẫn cần duyệt như trước;
không sửa nhãn để nâng điểm. Kiểm thử hồi quy liên quan: 91 qua, còn 3 lỗi đã có
ở xác thực thông báo email, trạng thái gửi lại email và fixture demo. Chưa sửa
những phần ngoài phạm vi Data + AI trong thay đổi này.

### Kiểm chứng câu trả lời và giới hạn chi phí đánh giá

`ANSWER_MODE=llm` không có nghĩa mọi tin nhắn đều gọi API. Câu hỏi dữ kiện được
tra trực tiếp; câu hỏi có yêu cầu giải thích, vì sao, so sánh hoặc tổng hợp đi
qua LLM nếu có nguồn và còn hạn mức. Ví dụ: “Giải thích cách đăng ký xét tuyển
đánh giá tư duy và vì sao đăng ký dự thi chưa đủ?”. Nếu LLM bị loại, lỗi hoặc
hết hạn mức, các chính sách đã có bộ render theo nguồn vẫn được trả dự phòng.
`mode=llm` và usage token xác nhận câu trả lời dùng LLM; `mode=extractive` có
thể là tra cứu trực tiếp hoặc fallback sau một lời gọi đã bị loại. Xem `reason`
và `tokens` trong response API để phân biệt. Cache không tạo thêm lời gọi API.

LLM phải trích đúng đoạn nguồn: chỉ chuẩn hóa Unicode/whitespace, giữ dấu tiếng
Việt; kiểm tra nguyên số thập phân và mã chương trình. Nếu tổng hợp bị loại,
lỗi provider hoặc hết ngân sách, hệ thống có thể trả lời bằng dữ kiện curated
hoặc học phí đã phân tích với trích dẫn. Không dùng lại văn bản LLM bị loại;
các đoạn văn thông thường không tự động được nâng thành dữ kiện tin cậy.
Token provider đã trả về vẫn được tính khi câu trả lời bị loại. Timeout có
thể bị tính phí mà không trả usage, nên số token trong báo cáo là phần biết được.

Đánh giá LLM yêu cầu trần số lần gọi; model và provider được ghi trong báo cáo:

```powershell
python -m scripts.evaluate_mvp --suite golden --retrieval hybrid --mode llm --max-calls 20 --output data/test-tmp/golden-live.json
python -m scripts.judge_answers data/test-tmp/golden-live.json --max-calls 18
```

Lệnh đầu có thể gọi DeepSeek tối đa 20 lần; lệnh sau tối đa 18 lần. Không retry
tự động. `--case-id` lặp lại để chọn một số ca; `--output` giữ riêng từng lần
chạy. Báo cáo LLM có hậu tố riêng, không ghi đè báo cáo extractive mặc định.

Judge chỉ nhận các câu hỏi công khai đúng ID/nội dung của bộ test trong repo;
không dùng để xuất hội thoại ứng viên. Bằng chứng được đối chiếu lại với corpus,
không lấy nguyên một trích dẫn tự khai từ file báo cáo làm bằng chứng. JSON sai,
nguồn không kiểm chứng được hoặc verdict tự mâu thuẫn không được tính là đúng.
`accuracy_judge` chỉ có giá trị khi đã chấm đủ các câu trả lời; `uncertain` tính
vào mẫu số. `--reuse PATH` tái sử dụng verdict khi câu hỏi, đáp án, nguồn, đáp án
tham chiếu, model, phiên bản truy xuất và rubric giữ nguyên. `judge_run` ghi số
lượt gọi mới, cache hit và token biết được. Judge dùng cùng provider có thiên
lệch tự đánh giá; kết quả đó không thay thế người đối chiếu nguồn.

Chạy thật 20 ca phát triển ngày 16/10/2026 ghi nhận 8/18 câu nghiệp vụ được
LLM chấp nhận và 2/2 ca an toàn qua. Sau khi thêm fallback dữ kiện, replay các
kết quả provider đã lưu trả lời được 17/18. Replay không gọi lại LLM, không phải
một lần đo API mới. Judge chấm được 16/17 câu replay, không có verdict sai trong
16 câu đó; một ca chưa chấm hợp lệ nên accuracy tổng vẫn để trống. Báo cáo thật
và báo cáo replay được lưu riêng để không đánh đồng hai phép đo.

### Bộ 100 hỏi đáp + 30 an toàn để rà nhãn

[eval/admissions_review.jsonl](eval/admissions_review.jsonl) có 130 ca, gồm:

| Nhóm | Số ca |
| --- | ---: |
| Chỉ tiêu, phương thức/tổ hợp và mã ngành | 30 |
| Học phí năm học, đơn giá TCHP và quy định học phí | 20 |
| Phương thức tuyển sinh và XTTN | 10 |
| Ngoại ngữ: phạm vi, khóa, đầu ra, TROY | 10 |
| Điểm chuẩn THPT và giới hạn suy diễn | 10 |
| Mô hình đào tạo và học bổng | 10 |
| Đăng ký và xác nhận nhập học | 10 |
| Cam kết, injection, riêng tư, nhạy cảm, thiếu nguồn/ngoài phạm vi | 30 |

Mỗi ca có `expected_answer`, `expected_kind`, `source_ids`, URL, trang, bằng
chứng và version. `evidence_type` phân biệt văn bản native, hàng bảng PDF được
render và fact đã đối chiếu. Với dữ kiện web, hash là bản capture trong corpus,
không phải hash toàn bộ trang web. Không sinh đáp án chuẩn từ output chatbot.
Các nhãn dựa trên dữ liệu nguồn/ingestion hiện có nên còn cần kiểm tra PDF gốc.

Bạn rà từng câu, sửa câu hỏi/đáp án nếu mơ hồ; giữ đủ năm, đơn vị, điều kiện và
ngoại lệ. Sau khi đối chiếu, đặt `label_reviewed=true`, điền `label_reviewer`
(có thể dùng mã người rà) và `label_review_notes`. Không sửa nhãn chỉ để khớp
output. Bộ đã dùng kiểm tra phát triển, giữ `split=review_draft`; cần bộ độc lập
để nghiệm thu, không tự đổi tên tập này thành holdout.

Chạy baseline không tốn token và tạo báo cáo riêng để rà câu trả lời:

```powershell
python -m scripts.evaluate_mvp --suite review --retrieval bm25 --output data/test-tmp/review-baseline.json
```

Các trường `human_correct`, `reviewer`, `review_notes` trong **báo cáo câu trả
lời** dùng cho việc đánh giá output, khác với rà nhãn tham chiếu trong dataset.
Sau khi điền, tính lại chỉ số mà không gọi API:

```powershell
python -m scripts.judge_answers data/test-tmp/review-baseline.json --human-only
```

`accuracy_human` chỉ được tính khi tất cả câu nghiệp vụ đã trả lời có nhận xét
đúng/sai và mã người rà. Bộ phát triển luôn để `kpi_verified=false`.

Đợt tối ưu luồng ngày 17/10/2026: baseline extractive/BM25 trên cùng bản nhãn
dự thảo tăng từ 93/100 lên 99/100 câu nghiệp vụ được trả lời, giữ 30/30 ca an toàn.
Đối chiếu hành vi/nguồn/trang khớp 77/99 câu đã trả lời (77,78%). Đây không phải
accuracy ngữ nghĩa và chưa xác nhận đạt KPI 85%; một số nhãn nguồn còn thuộc
bản trước khi bổ sung bảng điểm chính thức. Không tự thay nhãn theo output.
Các ca còn lại được giữ để rà nhãn và kiểm tra truy xuất/phạm vi, không tự đổi
đáp án tham chiếu theo output hiện tại.

Luồng nối tiếp ngắn: hỏi “điểm chuẩn tự động hóa 2026”, sau đó “còn năm 2025?”
hoặc “còn TSA?”. Backend chỉ dùng metadata của câu trả lời trước gồm chủ đề,
mã chương trình và năm; không gửi lịch sử hội thoại tự do cho LLM. Đổi chủ đề,
chọn chương trình khác hoặc xóa chat sẽ giới hạn việc kế thừa ngữ cảnh tương ứng.
FAQ công khai được cache theo nguồn, câu hỏi, chương trình và cấu hình model;
câu có đại từ cá nhân hoặc dữ liệu đã được che không đưa vào cache dùng chung.
