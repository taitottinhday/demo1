# Railway persistence

The application stores mutable state in SQLite: staff accounts, candidate accounts, tickets, ticket statuses, sessions, and audit history. A Railway deploy creates a new container filesystem, so that state must not live only under `/app/data`.

Configure the Railway service once:

1. Add a Railway Volume to the service.
2. Set its mount path to `/app/state`.
3. Add the variable `PERSISTENT_DATA_DIR=/app/state`.
4. Keep `MVP_DATA_DIR=data` so the bundled admissions sources remain available in the image.
5. Deploy and verify `/health`, then create a test ticket, restart/redeploy, and verify its status and owner remain present.

Production now refuses to start when `PERSISTENT_DATA_DIR` is missing or points at the knowledge directory. This prevents a deploy from appearing healthy while silently creating a blank database.

Do not mount the Volume over `/app/data`: that would hide the source PDF and `sources.md` copied into the image. The Docker Compose configuration uses `data/state` as the local equivalent.

This SQLite setup is intended for one Railway replica. If the service is scaled to multiple replicas, move the mutable state to PostgreSQL instead of sharing a SQLite file.

If the currently running deployment still has the old ephemeral database, copy it to the new Volume before the first restart if it is still accessible. Data already discarded with an old container cannot be reconstructed by the application.

## Kiểm tra triển khai và bàn giao Data + RAG + AI — 17/10/2026

### Kết quả đã kiểm tra

| Hạng mục | Kết quả |
| --- | --- |
| Railway `/health` | HTTP 200, `env=production`, `source_ready=true` |
| Railway `/api/v1/status` | HTTP 200, `mode=extractive`, 8 nguồn, 284 chunks, 68 chương trình |
| Vercel `/api/v1/status` | HTTP 200, cùng version/backend ở trên |
| Version online | `6991e9023c3e8a0d7e9deba96b40a91379a92d3a7c910643b58b8fd94a356176` |
| Bản nhánh tích hợp | 9 nguồn; hybrid runtime 1.047 chunks; khác bản online |
| Validator dữ liệu | Passed: 1.132 records, 1.065 chunks của snapshot chuẩn hóa; khác số chunk runtime |
| Lint đúng lệnh CI | Passed |
| Toàn bộ pytest sau sửa hội thoại | 208 passed |
| Eval 40 ca cũ dùng trong CI | Exit 1: 33/40 khớp nhãn; 25/30 câu nghiệp vụ trả lời, 10/10 ca an toàn qua |
| Docker build mới trên Linux/cloud | Chưa xác minh trong đợt kiểm tra này |
| Dashboard, quyền truy cập, nhánh autodeploy, secret, Volume/backup thực tế | Chưa xác minh; cần chủ tài khoản kiểm tra |

URL đã kiểm tra chỉ đọc: `https://demo1-production-f54e.up.railway.app/health`,
`https://demo1-production-f54e.up.railway.app/api/v1/status`,
`https://demo1-alpha-tan.vercel.app/api/v1/status`.
Không đăng nhập production, không gửi chat, không gọi DeepSeek để thực hiện kiểm tra.
`mode=extractive` xác nhận cấu hình trả lời hiện tại, không cho biết có lưu key trên server hay chưa.

### 1. Chốt phạm vi và các điều kiện trước merge — Data/AI + người rà nguồn

Nhánh hiện tại là `feature/data-ai-integration`; kiểm tra tên thực tế bằng
`git branch --show-current` trước push. Không cần đổi tên nhánh để triển khai.
Đối chiếu các ca CI chưa khớp trong `eval/cases.json`:

| Ca | Vấn đề cần rà |
| --- | --- |
| Q14 | Nhãn kỳ vọng có lệ phí TSA, runtime từ chối vì nguồn scan chưa đủ căn cứ; xác minh nguồn hợp lệ trước khi mở trả lời |
| Q15 | Câu hỏi phí xác thực chứng chỉ đang bị hiểu thành điều kiện ngoại ngữ theo ngành |
| Q17 | Câu hỏi hệ số tổ hợp K01 đang bị hỏi lại chương trình |
| Q18 | Câu hỏi điều kiện ngoại ngữ nhóm tiên tiến đang yêu cầu mã cụ thể; cần xác định phạm vi nhóm từ nguồn |
| Q21, Q22 | Nhãn cũ kỳ vọng từ chối học bổng/điểm chuẩn IT1; hiện đã có nguồn bổ sung, cần người đối chiếu nhãn |
| Q26 | Có trả lời đúng chủ đề nhưng chuỗi kiểm tra cũ `không nêu IT1` không khớp cách diễn đạt mới; cần kiểm tra nội dung và phép đo |

Không bỏ gate, dùng `continue-on-error`, hoặc tự đổi nhãn theo output để merge.
Chạy lại các bước tương đương CI sau khi xử lý; lưu báo cáo eval mới riêng:

```powershell
python -X utf8 scripts/validate_admissions_data.py
python -m ruff check src/ tests/ scripts/ingest_sources.py scripts/evaluate_mvp.py scripts/check_browser.py
python -m pytest tests -q
python -m scripts.evaluate_mvp --retrieval bm25 --output data/test-tmp/premerge-ci.json
```

Đánh giá phát triển 130 ca hiện có ở
[admissions-review-premerge.json](../eval/results/admissions-review-premerge.json).
99/100 câu nghiệp vụ được trả lời và 30/30 ca an toàn qua; chưa có accuracy do người
rà xác nhận. Hoàn thành nhãn và bộ nghiệm thu độc lập theo
[README](../README-MVP.md#bàn-giao-trước-khi-merge--17102026) trước tuyên bố đạt KPI.

### 2. Chuẩn bị môi trường — người quản lý Railway

Trước khi cập nhật production, xác nhận backup có thể phục hồi của SQLite và
PostgreSQL; thử trên môi trường staging với state/database riêng. Không dùng
chung dữ liệu ứng viên thật cho kiểm thử. Ghi lại commit và cấu hình đang chạy.

Trong service backend Railway:

1. Source phải trỏ đúng repository, root directory là gốc repo, branch theo dõi `main`.
2. Xác nhận builder dùng `Dockerfile`, không ghi đè Start Command nếu không cần.
3. Gắn Volume `/app/state`, giữ một replica vì state hiện dùng SQLite.
4. Healthcheck path `/health`. Healthcheck này không chứng minh DeepSeek hay vector index hoạt động.
5. Đặt các biến sau qua Variables, không đưa giá trị bí mật vào Git/chat:

```dotenv
APP_ENV=production
MVP_DATA_DIR=data
PERSISTENT_DATA_DIR=/app/state
SECURE_COOKIES=true
PUBLIC_BASE_URL=https://<ten-mien-frontend-thuc-te>
CORS_ORIGINS=https://<ten-mien-frontend-thuc-te>
WITH_RAG=true
RETRIEVAL_MODE=bm25
RAG_MODEL_CACHE=/app/state/models
RAG_DATABASE_URL=<URL-PostgreSQL-cloud-co-pgvector>
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=<nhap-truc-tiep-trong-secret>
DEEPSEEK_MODEL=deepseek-flash
ANSWER_MODE=extractive
LLM_DAILY_LIMIT=20
LLM_TIMEOUT=15
LLM_MAX_OUTPUT_TOKENS=1200
```

`20` là mức khởi động có kiểm soát, cần người vận hành điều chỉnh theo nhu cầu;
đây là trần số lượt đặt chỗ gọi, không phải trần tiền. `WITH_RAG=true` được dùng
ở build qua Docker ARG; thay biến này phải rebuild image. Khóa DeepSeek không
được dùng làm build ARG hoặc đưa lên frontend.

Giữ/cấu hình riêng `AUTH_SECRET` (>=32 ký tự ngẫu nhiên), `STAFF_PASSWORD` và
`ADMIN_PASSWORD` riêng (>=12 ký tự), email provider hợp lệ (Resend hoặc SMTP).
Đây là điều kiện khởi động production hiện có; không thay secret của hệ thống đang
chạy tùy tiện. Nếu dùng OAuth, bên backend xác nhận callback theo domain thực tế.
Các origin frontend được phép phải có trong `CORS_ORIGINS` để thao tác chat không bị 403.

PostgreSQL cloud phải hỗ trợ extension `vector`, có persistent storage/backup;
người vận hành kiểm tra `CREATE EXTENSION IF NOT EXISTS vector` và phân quyền tạo
bảng cho tài khoản build. Ưu tiên private networking cho kết nối backend–database.
Không dùng URL `127.0.0.1:55432` từ `.env` local: đó là Docker trên máy phát triển.
Giữ chuỗi kết nối/SSL đúng yêu cầu nhà cung cấp. `DATABASE_URL` của template không
thay thế `RAG_DATABASE_URL`; state ứng dụng hiện vẫn là SQLite trên Volume.

### 3. Kiểm tra frontend — người quản lý Vercel

1. Project kết nối đúng repo, Root Directory `src/web`, phục vụ static assets
   (Framework Preset Other; không có bước build Next.js trong cấu trúc hiện tại).
2. Production environment theo dõi `main`; xác nhận không vô hiệu hóa autodeploy.
3. `src/web/vercel.json` hiện rewrite `/api/*` tới
   `https://demo1-production-f54e.up.railway.app/api/*`. Nếu backend đổi domain,
   sửa rewrite cùng PR trước deploy.
4. Dùng tên miền frontend thực tế cho `PUBLIC_BASE_URL` và `CORS_ORIGINS` ở backend.
5. Không cấu hình `DEEPSEEK_API_KEY` trong frontend hoặc biến công khai `NEXT_PUBLIC_*`.

Nếu cả hai nền tảng đã theo dõi `main`, push/merge sẽ có thể kích hoạt deploy;
merge local chưa push không kích hoạt. Railway có thể bật Wait for CI sau khi gate
ở bước 1 đã qua. Chưa có workflow trong repo tự tạo database/cache hoặc build index
cloud. Không xem autodeploy ứng dụng là tự đồng bộ mọi thành phần RAG.

### 4. Đưa code lên và khởi tạo RAG cloud — Data/AI + DevOps

Sau khi bước 1 qua và chủ môi trường đã chuẩn bị cấu hình, push nhánh hiện tại và
mở PR vào `main` theo quy trình nhóm. Chọn đúng commit đã review; không merge thẳng
khi CI còn lỗi. Staging phải chạy đúng commit/image sẽ phát hành.

Lần đầu deploy backend dùng `RETRIEVAL_MODE=bm25`, `ANSWER_MODE=extractive` như bước 2
để chưa phát sinh phí model và chưa nhận nhầm là hybrid sẵn sàng. Sau khi deploy
Docker có RAG thành công, vào **container đang chạy có Volume `/app/state` đã mount**
bằng Railway SSH của service/environment tương ứng. Ví dụ từ máy đã cài và đăng nhập CLI:

```text
railway link
railway ssh
```

Xác nhận đúng service/environment, rồi chạy bên trong container, tại `/app`:

```sh
python -m scripts.build_rag_index
```

Lệnh này tải hai model đúng revision và xây index nguồn công khai vào PostgreSQL;
không gọi DeepSeek. Chạy bằng user `appuser` nếu shell đang là root để cache có
quyền sở hữu phù hợp. Cần mạng tải model lần đầu, đủ RAM/disk và thời gian CPU.
Cache phải ở `/app/state/models` để còn sau redeploy. Không chạy trên máy local bằng
`railway run` rồi cho rằng model đã nằm trong Volume cloud. Không đặt lệnh tải cache
vào build image trong khi runtime trỏ sang Volume trống.

Sau khi build hoàn tất, đổi `RETRIEVAL_MODE=hybrid`, deploy/restart và kiểm tra:

- `/api/v1/status`: `status=ready`, 9 nguồn, 68 chương trình; trường
  `source.retrieval=hybrid`, không phải `bm25_fallback`.
- Đăng nhập cán bộ, gọi cùng origin `GET /api/v1/staff/ai/metrics`:
  `source_ready=true`, `retrieval_index_ready=true`.
- Nguồn hiển thị mới và PDF/web mở được qua frontend.

Nếu chỉ mục không sẵn sàng, xem log theo loại lỗi, quyền cache và kết nối database;
không chép secret/log chứa dữ liệu cá nhân vào issue công khai. Thay nguồn/model revision
cần build lại index rồi restart để tiến trình nạp bản mới. Giữ snapshot cũ cho rollback.
Quy trình này có bước khởi tạo/cập nhật index thủ công; chưa tự động toàn phần.

### 5. Bật DeepSeek và thử nghiệm sau deploy — Data/AI

Sau kiểm tra RAG, đổi `ANSWER_MODE=llm` trên Railway rồi redeploy. Xác nhận
`/api/v1/status` trả `mode=llm`; trạng thái này chưa chứng minh key hợp lệ.
Trên staging, dùng DevTools Network xem JSON response `/api/v1/chat`:

| Chuỗi thử | Kỳ vọng |
| --- | --- |
| Học phí ngành vật liệu → MS3 bạn ơi | Hỏi chọn chương trình, sau đó học phí MS3 có nguồn |
| Điểm chuẩn tự động hóa 2026 → còn năm 2025? → còn TSA? | Đúng EE2, năm/phương thức; không dùng điểm năm khác |
| Điểm chuẩn ngành trí tuệ nhân tạo | Nhận diện IT-E10, đúng bảng chính thức |
| Điều kiện ngoại ngữ CH1 / EEE8 | Phân biệt chương trình và đầu vào/đầu ra |
| Giải thích cách đăng ký xét tuyển đánh giá tư duy và vì sao đăng ký dự thi chưa đủ? | Có cơ hội đi nhánh LLM; xem `mode`, `reason`, `tokens`, `cached` thực tế |
| Cam kết chắc chắn trúng tuyển / yêu cầu nhạy cảm | Không cam kết, có hướng chuyển cán bộ |
| Xóa chat rồi hỏi “còn năm 2025?” | Không kế thừa chương trình/chủ đề đã xóa |

Một câu tổng hợp có thể phát sinh phí. Người vận hành kiểm tra usage DeepSeek và
giới hạn trước khi thử. Câu tra cứu trực tiếp và cache thường không gọi API;
`mode=extractive` ở một câu không đủ kết luận provider hỏng. Khi cần chứng minh nối
API, kiểm tra một câu mới có tổng hợp, `cached=false`, `mode=llm` và token usage;
nếu fallback, xem reason thay vì coi là thành công. Không retry hàng loạt hoặc bỏ
kiểm chứng nguồn để tăng tỷ lệ dùng LLM.

Thử một ticket với tài khoản kiểm thử do nhóm quản lý, nhận/xử lý ở giao diện cán bộ,
kiểm tra thông báo và tồn tại sau restart. Không gửi thông báo tới ứng viên thật.
Đo tải và chi phí trên cấu hình cloud thực tế trước cam kết đáp ứng mùa cao điểm;
p50/p95 local và trần lượt gọi không phải benchmark tải hay giới hạn tiền.

### 6. Bàn giao và vận hành — các bên ký nhận

| Bên nhận | Nội dung nhận và tự xác nhận |
| --- | --- |
| Data/AI | Nguồn/provenance, bộ lọc hợp lệ, danh mục 68 chương trình, logic RAG/guardrails, eval và giới hạn đã biết |
| Backend/DevOps | Commit/image đã deploy, biến môi trường qua secret manager, quyền Railway/PostgreSQL, Volume/backup, lệnh build index, rollback |
| Frontend | Quy tắc `/api` rewrite, domain/origin, cách trình bày nguồn, kiểm thử chuỗi chat |
| Cán bộ tuyển sinh/QA | Đối chiếu nhãn và nguồn, xác nhận câu từ chối sai, quy trình nhận ticket; nghiệm thu KPI độc lập |

Ghi vào PR/biên bản: commit SHA; URL staging/production; version nguồn và index;
người quản lý tài khoản/quota/key; vị trí backup và lần thử phục hồi; ngày/ai rà nhãn;
kết quả smoke test/API/metrics; tồn đọng và người chịu trách nhiệm. Chuyển quyền qua
lời mời thành viên/secret manager, không gửi nguyên `.env`, SQLite hoặc hội thoại.

Khi có sự cố LLM, đổi `ANSWER_MODE=extractive` để tiếp tục tra cứu nguồn;
khi có sự cố vector, đổi `RETRIEVAL_MODE=bm25` rồi restart và ghi nhận suy giảm.
Rollback code/frontend về commit/image đã biết tốt; rollback index theo đúng version
nguồn, giữ state/backup độc lập, không xóa Volume. Rollback cấu hình/ứng dụng không
đồng nghĩa đã phục hồi dữ liệu. Chỉ kết thúc bàn giao production khi các bên nhận đã
xác nhận đủ mục ở trên và các gate còn lỗi được xử lý.

Tài liệu nền tảng dùng đối chiếu:
[Railway Docker ARG](https://docs.railway.com/builds/dockerfiles),
[Railway autodeploy và Wait for CI](https://docs.railway.com/deployments/github-autodeploys),
[Railway Volume](https://docs.railway.com/volumes),
[Railway SSH](https://docs.railway.com/cli/ssh),
[Vercel Git và production branch](https://vercel.com/docs/git).
