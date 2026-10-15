# ADMIN_SPEC: Phần Admin của "Trợ lý tuyển sinh AI"

> File này mô tả phạm vi, quy tắc và đặc tả cho role Admin. Dùng làm ngữ cảnh cho Claude trong VS Code và làm tài liệu chung của nhóm.

## 1. Bối cảnh

- Dự án: chatbot tuyển sinh tư vấn ứng viên 24/7, có handover cho cán bộ khi bot không chắc chắn hoặc câu hỏi nhạy cảm.
- Stack: FastAPI (backend, kiểm tra phân quyền và ownership), SQLite, Next.js (frontend).
- 3 role: người dùng / ứng viên, cán bộ tuyển sinh, admin.
- Luồng ticket tối giản:

```
waiting  --claim-->  in_progress  --resolve-->  resolved
                         |
                         +--reject-->  rejected
```

- Ticket được tạo khi: AI độ tự tin thấp, câu hỏi nhạy cảm, hoặc ứng viên yêu cầu gặp cán bộ.
- Phần AI (RAG, ngưỡng tự tin, tài liệu tuyển sinh, guardrails) do thành viên khác phụ trách. **Phần Admin không sửa các phần đó.**

## 2. Phạm vi Admin (4 chức năng)

| # | Chức năng | Mô tả |
|---|---|---|
| 1 | Xem toàn bộ ticket | Danh sách có lọc theo trạng thái và cán bộ. Xem chi tiết một ticket kèm hội thoại, câu trả lời AI và nguồn |
| 2 | Quản lý cán bộ | Tạo tài khoản, khóa hoặc mở, xem số ticket đang giữ |
| 3 | Xem metrics và lịch sử | Thống kê tổng quan và dòng thời gian của từng ticket |
| 4 | Phân công lại | Đổi cán bộ phụ trách hoặc trả ticket về `waiting` |

Ngoài phạm vi: cấu hình ngưỡng tự tin, danh sách chủ đề nhạy cảm, quản lý và index tài liệu tuyển sinh (thuộc bên AI).

## 3. Quy tắc bắt buộc

1. Mọi endpoint `/admin/*` kiểm tra `role = admin` ở phía server. Không chỉ ẩn nút trên giao diện.
2. Mỗi lần đổi trạng thái hoặc phân công đều ghi một dòng vào `ticket_events`.
3. Cập nhật có điều kiện để tránh tranh chấp, rồi kiểm tra số dòng bị ảnh hưởng. Nếu bằng 0 thì trả `409`.
   Ví dụ: `UPDATE tickets SET officer_id=? WHERE id=? AND officer_id=? AND status='in_progress'`.
4. Ticket `resolved` hoặc `rejected` không được phân công lại.
5. Khóa cán bộ đang giữ ticket: tự động trả các ticket đó về `waiting`, đặt `officer_id = NULL` và ghi sự kiện `reassigned`. Nếu repo đã có quy ước khác thì theo quy ước đó và báo lại.
6. Cán bộ chỉ được resolve hoặc reject ticket do chính mình claim. Admin được can thiệp nhưng phải ghi `ticket_events` để biết ai đã can thiệp.
7. Không thu thập dữ liệu cá nhân ngoài những gì repo đang lưu.
8. Mã lỗi nhất quán: `401` chưa đăng nhập, `403` sai role, `404` không tìm thấy, `409` dữ liệu đã đổi hoặc trạng thái không hợp lệ, `422` dữ liệu đầu vào sai.

## 4. Schema gợi ý (SQLite)

> Đây là đề xuất. Cần đối chiếu với model đã có trong repo trước khi tạo. Không sửa bảng của người khác nếu chưa thống nhất.

```sql
CREATE TABLE users (
  id          INTEGER PRIMARY KEY,
  name        TEXT NOT NULL,
  email       TEXT UNIQUE NOT NULL,
  role        TEXT NOT NULL CHECK (role IN ('user','officer','admin')),
  active      INTEGER NOT NULL DEFAULT 1,
  created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tickets (
  id                INTEGER PRIMARY KEY,
  user_id           INTEGER NOT NULL REFERENCES users(id),
  question          TEXT NOT NULL,
  ai_answer         TEXT,
  ai_sources        TEXT,            -- JSON: danh sách nguồn trích dẫn
  handover_reason   TEXT CHECK (handover_reason IN ('low_confidence','sensitive','user_request')),
  confidence_score  REAL,
  status            TEXT NOT NULL DEFAULT 'waiting'
                    CHECK (status IN ('waiting','in_progress','resolved','rejected')),
  officer_id        INTEGER REFERENCES users(id),
  officer_reply     TEXT,
  created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  claimed_at        TEXT,
  resolved_at       TEXT
);

CREATE TABLE ticket_events (
  id                 INTEGER PRIMARY KEY,
  ticket_id          INTEGER NOT NULL REFERENCES tickets(id),
  actor_id           INTEGER NOT NULL REFERENCES users(id),
  action             TEXT NOT NULL
                     CHECK (action IN ('created','claimed','resolved','rejected','reassigned')),
  from_officer_id    INTEGER REFERENCES users(id),
  to_officer_id      INTEGER REFERENCES users(id),
  note               TEXT,
  created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tickets_status  ON tickets(status);
CREATE INDEX idx_tickets_officer ON tickets(officer_id);
CREATE INDEX idx_events_ticket   ON ticket_events(ticket_id);
```

### Bảng log chat (do bên AI ghi, Admin chỉ đọc)

Cần để tính tỷ lệ trả lời trực tiếp và tỷ lệ chuyển cán bộ (KPI của đề).

```sql
CREATE TABLE chat_logs (
  id                INTEGER PRIMARY KEY,
  user_id           INTEGER REFERENCES users(id),
  question          TEXT NOT NULL,
  answered_directly INTEGER NOT NULL,   -- 1: bot tự trả lời, 0: không
  handed_over       INTEGER NOT NULL,   -- 1: đã tạo ticket
  confidence_score  REAL,
  created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

## 5. Endpoint

Tất cả yêu cầu header xác thực và role `admin`.

### 5.1 Ticket

| Method | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/admin/tickets` | Danh sách. Query: `status`, `officer_id`, `page`, `page_size` |
| GET | `/admin/tickets/{id}` | Chi tiết: câu hỏi, câu trả lời AI, nguồn, lý do chuyển, cán bộ, mốc thời gian |
| GET | `/admin/tickets/{id}/history` | Dòng thời gian từ `ticket_events`, sắp theo thời gian tăng dần |
| POST | `/admin/tickets/{id}/reassign` | Body: `{ "to_officer_id": int \| null, "note": str }`. `null` nghĩa là trả về `waiting` |

Quy tắc `reassign`:
- Chỉ áp dụng khi ticket đang `waiting` hoặc `in_progress`. Ngược lại trả `409`.
- Cán bộ nhận phải có `role = officer` và `active = 1`. Ngược lại trả `422`.
- Ghi sự kiện `reassigned` với `from_officer_id` và `to_officer_id`.
- Khi gán cho cán bộ mới thì `status = in_progress`. Khi `to_officer_id = null` thì `status = waiting` và `claimed_at = NULL`.

### 5.2 Cán bộ

| Method | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/admin/officers` | Danh sách kèm `open_tickets` (số ticket đang giữ) |
| POST | `/admin/officers` | Tạo tài khoản cán bộ. Body: `name`, `email`, mật khẩu theo cơ chế auth của repo |
| PATCH | `/admin/officers/{id}` | Sửa tên hoặc `active`. Khóa (`active = 0`) thì áp dụng quy tắc số 5 |

### 5.3 Metrics

| Method | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/admin/metrics` | Query: `from`, `to` (ngày). Trả các chỉ số bên dưới |

Chỉ số trả về:
- `tickets_by_status`: số ticket theo từng trạng thái.
- `avg_wait_seconds`: trung bình `claimed_at - created_at`.
- `avg_resolve_seconds`: trung bình `resolved_at - claimed_at`.
- `reject_rate`: `rejected / (resolved + rejected)`.
- `officer_load`: mỗi cán bộ đang giữ bao nhiêu ticket.
- `stale_waiting`: danh sách ticket `waiting` quá ngưỡng thời gian (mặc định 24 giờ, cấu hình được).
- `direct_answer_rate` và `handover_rate`: tính từ `chat_logs`. Nếu chưa có bảng này thì trả `null`.

## 6. Giao diện admin

Các màn hình tối thiểu:
1. **Tổng quan:** thẻ chỉ số, biểu đồ ticket theo trạng thái, danh sách ticket chờ quá lâu.
2. **Danh sách ticket:** bảng có lọc và phân trang. Bấm vào dòng để xem chi tiết.
3. **Chi tiết ticket:** hội thoại, câu trả lời AI kèm nguồn, lý do chuyển, dòng thời gian lịch sử, nút phân công lại.
4. **Cán bộ:** bảng cán bộ, nút tạo mới, công tắc khóa hoặc mở, số ticket đang giữ.

Khi khóa cán bộ đang giữ ticket, hiển thị hộp xác nhận nêu rõ "N ticket sẽ được trả về hàng chờ".

## 7. Điểm cần thống nhất với bên AI

| Nội dung | Lý do |
|---|---|
| Khi AI chuyển ticket, ghi `handover_reason` và `confidence_score` | Hiển thị lý do chuyển và thống kê theo lý do |
| Lưu `ai_answer` và `ai_sources` trong ticket | Admin xem chi tiết mà không phải gọi lại AI |
| Mỗi lượt chat ghi một dòng `chat_logs` | Tính tỷ lệ trả lời trực tiếp và tỷ lệ chuyển |
| Ai sở hữu bảng nào, ai được ghi vào bảng nào | Tránh xung đột schema |

## 8. Cách làm việc với Claude trong VS Code

### Bước 1: đọc repo và báo cáo (chưa viết code)
- Cấu trúc thư mục, ORM đang dùng (SQLAlchemy, SQLModel hay SQL thuần), cách xác thực và phân quyền hiện có.
- Bảng và model đã có (`users`, `tickets`, `ticket_events`, `chat_logs`), cái nào thiếu hoặc thiếu cột.
- Chỗ có thể xung đột với phần của người khác (bảng, file, route).
- Đề xuất danh sách file sẽ tạo hoặc sửa, và thay đổi schema cần thống nhất với bên AI.
- Sau đó dừng lại, chờ xác nhận.

### Bước 2: triển khai (sau khi xác nhận)
1. Migration hoặc model cho các bảng và cột còn thiếu. Không đổi bảng của người khác nếu chưa hỏi.
2. Router `/admin` với 4 nhóm endpoint trên, schema request và response bằng Pydantic, mã lỗi nhất quán.
3. Test cho:
   - phân quyền (không phải admin thì `403`)
   - reassign đúng và sai trạng thái
   - tranh chấp (cập nhật có điều kiện trả `409`)
   - khóa cán bộ đang giữ ticket
   - tính metrics với dữ liệu mẫu
4. Giao diện admin theo mục 6.
5. Script seed dữ liệu demo: vài cán bộ, ticket đủ 4 trạng thái, vài sự kiện lịch sử.

### Nguyên tắc
- Làm từng bước nhỏ, mỗi bước chạy được và có test.
- Không sửa code ngoài phạm vi Admin. Nếu cần, hỏi trước.
- Bám phong cách code hiện có trong repo.

## 9. Kịch bản demo Admin (khoảng 2 phút)

1. Mở danh sách ticket, lọc `waiting`, mở một ticket xem chi tiết (lý do chuyển, nguồn AI).
2. Mở trang tổng quan, chỉ ra thời gian chờ trung bình và tải của từng cán bộ.
3. Phân công lại một ticket `in_progress` sang cán bộ khác, mở lịch sử để thấy sự kiện vừa ghi.
4. Khóa một cán bộ đang giữ ticket, cho thấy ticket trở về hàng chờ.

## 10. Việc cần chốt

- [ ] Nhóm dùng ORM nào?
- [ ] Cơ chế xác thực hiện tại (JWT, session)?
- [ ] Ngưỡng "ticket chờ quá lâu" (mặc định 24 giờ có ổn không)?
- [ ] Bên AI có đồng ý ghi `handover_reason`, `confidence_score`, `chat_logs` không?
- [ ] Khóa cán bộ đang giữ ticket: tự trả về `waiting` hay chặn khóa?
