# Kiến trúc MVP triển khai — 04/10/2026

```mermaid
flowchart LR
    C[Ứng viên / Cán bộ] --> UI[HTML CSS JS cùng origin]
    UI --> API[FastAPI + cookie session + kiểm tra quyền]
    API --> CHAT[Guardrails / ngữ cảnh chương trình]
    CHAT --> RET[BM25 + rerank theo intent]
    RET -->|Đọc và xếp hạng| KB[Đoạn văn và dòng bảng có trang nguồn]
    RET --> ANS{Chế độ trả lời}
    ANS --> EXT[Trích nội dung tài liệu]
    ANS --> LLM[OpenAI Responses tùy chọn]
    LLM --> CHECK[Schema / quote / dữ kiện số]
    CHECK --> API
    EXT --> API
    API --> HITL[Đồng ý handover / nhận / phản hồi / đóng]
    API --> COMP[So sánh 2–3 chương trình]
    COMP --> RET
    API --> FEEDBACK[Đánh giá câu trả lời theo request_id]
    FEEDBACK --> DB
    HITL --> DB[(SQLite phiên ticket metric)]
    PDF[PDF 51 trang + sources.md] --> INGEST[PyMuPDF / bảng gộp / SHA256]
    INGEST --> KB
```

Không có Next.js/pgvector trong demo local. Xem [README MVP](../README-MVP.md) cho phạm vi nguồn và giới hạn đánh giá. Các file agent LangGraph mẫu không được gọi trong API chat MVP.

| Thành phần | Triển khai |
|---|---|
| Giao diện | `src/web/`, JavaScript gọi API cùng origin |
| API và quyền truy cập | `src/api/routes.py`, cookie HttpOnly/SameSite, kiểm tra phiên sở hữu |
| Nguồn và retrieval | `src/services/knowledge.py`, PyMuPDF, BM25, rerank intent, phiên bản SHA256 |
| Trả lời và guardrails | `src/services/admissions.py`, trích nguồn hoặc OpenAI Responses có kiểm tra quote |
| Lưu trữ và handover | `src/services/store.py`, SQLite, nhận độc quyền, idempotency, TTL |
| Đánh giá | `eval/cases.json`, `scripts/evaluate_mvp.py`, báo cáo nhãn tự động và trường duyệt thủ công |

## Data flow — chat và trích nguồn

```mermaid
sequenceDiagram
    actor U as Ứng viên
    participant UI as Web
    participant API as FastAPI
    participant AI as Admissions
    participant K as Knowledge
    participant DB as SQLite
    U->>UI: Nhập câu hỏi và chương trình tùy chọn
    UI->>API: POST /api/v1/chat
    API->>DB: Phiên, rate limit và ngữ cảnh
    API->>AI: Câu hỏi đã ẩn PII, mã chương trình
    AI->>AI: Guardrail, phạm vi, cache
    alt Thiếu nguồn hoặc ngoài phạm vi
        AI-->>API: Fallback không dẫn nguồn không liên quan
    else Có nguồn
        AI->>K: Truy xuất và xếp hạng chunks
        K-->>AI: Nội dung, trang và phiên bản nguồn
        AI->>AI: Trình bày hoặc LLM tùy chọn và kiểm tra quote
        AI-->>API: response, sources, kind, reason
    end
    API->>DB: Lưu chat, request_id và metric
    API-->>UI: Câu trả lời và citations
    UI-->>U: Hiển thị nguồn và nút đánh giá / chuyển cán bộ
```

## Data flow — handover end-to-end

```mermaid
sequenceDiagram
    actor U as Ứng viên
    participant UI as Web ứng viên
    participant API as API và SQLite
    actor S as Cán bộ
    U->>UI: Chọn câu hỏi, sửa nội dung, đồng ý chia sẻ
    UI->>API: POST /handover, request_key chống trùng
    API-->>UI: Ticket waiting
    S->>API: Đăng nhập, xem hàng chờ
    S->>API: claim
    API-->>S: in_progress và owner
    alt Trả lời
        S->>API: resolve kèm phản hồi
        API-->>S: resolved
    else Không phù hợp
        S->>API: reject kèm lý do
        API-->>S: rejected
    end
    UI->>API: GET /tickets mỗi 15 giây khi trang hiển thị
    API-->>UI: Trạng thái và phản hồi thuộc phiên
    UI-->>U: Báo phản hồi mới, mở danh sách để đọc
```

## Nguồn, persistence và giới hạn

PDF và `sources.md` được đọc lúc khởi động; PyMuPDF tạo chunks có số trang và SHA256, giữ chỉ mục trong process và ghi `data/processed/knowledge.json` để kiểm tra. Dữ liệu xử lý tái tạo được. SQLite lưu phiên, lịch sử chat, đánh giá, ticket, metric và hạn mức; chỉ lưu hash token đăng nhập. Database và `.env` không commit.

Cán bộ chỉ nhận nội dung ticket ứng viên đồng ý gửi, không nhận nguyên lịch sử chat. Dấu phản hồi đã xem lưu trong localStorage; dữ liệu phản hồi và quyền xem ticket nằm trên backend. Cache và chỉ mục theo process; chưa kiểm chứng nhiều worker hoặc tải cao. Kiểm tra quote/numbers không thay thế xác minh độ chính xác ngữ nghĩa.

Tài liệu liên quan: [README MVP](../README-MVP.md), [manual evidence](../eval/manual-tests.md).
