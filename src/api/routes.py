import re
import secrets
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from src.services.admissions import redact
from src.services.product_features import compare_programs

router = APIRouter()


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    program: str | None = Field(default=None, max_length=30)

    @field_validator("message")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("Cần nhập nội dung.")
        return value.strip()


class TicketInput(BaseModel):
    summary: str = Field(min_length=1, max_length=3000)
    consent: bool = False
    reason: str = Field(default="user_request", max_length=60)
    request_key: str = Field(min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class ReplyInput(BaseModel):
    reply: str = Field(min_length=1, max_length=4000)


class FeedbackInput(BaseModel):
    rating: Literal["helpful", "incorrect"]


class ComparisonInput(BaseModel):
    codes: list[str] = Field(min_length=2, max_length=3)


@router.post("/programs/compare")
def comparison(body: ComparisonInput, request: Request):
    knowledge = runtime(request)["knowledge"]
    codes = [code.upper().strip() for code in body.codes]
    if len(set(codes)) != len(codes) or not set(codes).issubset({p["code"] for p in knowledge.programs}):
        raise HTTPException(422, "Chọn 2–3 mã chương trình khác nhau có trong nguồn.")
    return {"programs": compare_programs(knowledge, codes), "year": 2026}


def runtime(request: Request):
    return request.app.state.runtime


def candidate(request: Request, response: Response):
    rt = runtime(request)
    token, row = rt["store"].session(request.cookies.get("candidate"), rt["settings"].session_hours)
    response.set_cookie(
        "candidate",
        token,
        httponly=True,
        samesite="strict",
        secure=rt["settings"].secure_cookies,
        max_age=rt["settings"].session_hours * 3600,
    )
    return row


def safe_ticket(ticket):
    return {k: v for k, v in ticket.items() if k not in ["session", "request_key"]}


def staff(request: Request):
    user = runtime(request)["store"].staff_user(request.cookies.get("staff"))
    if not user:
        raise HTTPException(401, "Bạn cần đăng nhập cán bộ.")
    return user


@router.post("/answers/{request_id}/feedback")
def answer_feedback(request_id: str, body: FeedbackInput, request: Request, row=Depends(candidate)):
    if not runtime(request)["store"].feedback(row["id"], request_id, body.rating):
        raise HTTPException(404, "Không tìm thấy câu trả lời trong phiên của bạn.")
    return {"rating": body.rating}


@router.get("/session")
def session(request: Request, row=Depends(candidate)):
    rt = runtime(request)
    return {
        "messages": rt["store"].messages(row["id"]),
        "program": row["context"],
        "tickets": [safe_ticket(t) for t in rt["store"].tickets(row["id"])],
    }


@router.delete("/session/messages")
def clear(request: Request, row=Depends(candidate)):
    runtime(request)["store"].clear(row["id"])
    return {
        "message": "Đã xóa ngữ cảnh và lịch sử chat. Ticket đã gửi vẫn được giữ; liên hệ cán bộ nếu cần xóa ticket."
    }


@router.get("/status")
def status(request: Request):
    rt = runtime(request)
    return {
        "status": "ready" if rt["knowledge"].chunks else "source_unavailable",
        "mode": rt["settings"].answer_mode,
        "source": rt["knowledge"].manifest,
        "source_error": rt.get("source_error"),
        "programs": len(rt["knowledge"].programs),
        "chunks": len(rt["knowledge"].chunks),
    }


@router.get("/programs")
def programs(request: Request):
    return runtime(request)["knowledge"].programs


@router.get("/guide")
def guide(request: Request):
    k = runtime(request)["knowledge"]
    source = next((c for c in k.chunks if c["page"] == 18 and "tsa.hust.edu.vn/dk" in c["text"]), None)
    if not source:
        raise HTTPException(503, "Chưa có nguồn cho hướng dẫn đăng ký ĐGTD.")
    return {
        "title": "Chuẩn bị xét tuyển theo Đánh giá tư duy",
        "note": "Danh sách tự kiểm tra dựa trên mục 6.2, PDF trang 18. Không phải hồ sơ đã nộp hoặc xác nhận đủ điều kiện.",
        "steps": [
            {
                "title": "Đối chiếu điều kiện dự tuyển",
                "text": "Tài liệu nêu: đã tốt nghiệp THPT, có điểm ĐGTD năm 2025 hoặc 2026 và đạt ngưỡng nhận hồ sơ do HUST quy định.",
                "url": "/api/v1/source/pdf#page=18",
            },
            {
                "title": "Phân biệt đăng ký dự thi và xét tuyển",
                "text": "Đăng ký dự thi ĐGTD tại địa chỉ được tài liệu dẫn; việc dự thi không thay thế đăng ký nguyện vọng.",
                "url": "https://tsa.hust.edu.vn/dk",
            },
            {
                "title": "Đăng ký nguyện vọng theo kế hoạch chung",
                "text": "Tài liệu dẫn hệ thống của Bộ để đăng ký nguyện vọng bằng tài khoản thí sinh. Kiểm tra thông báo đang có hiệu lực trước thao tác.",
                "url": "https://thisinh.thitotnghiepthpt.edu.vn/Account/Login",
            },
        ],
        "source": k.citation(source),
    }


@router.get("/source/pdf")
def pdf(request: Request):
    k = runtime(request)["knowledge"]
    if not k.pdf or not k.pdf.exists():
        raise HTTPException(404, "Chưa có tài liệu nguồn.")
    return FileResponse(k.pdf, media_type="application/pdf", content_disposition_type="inline", filename=k.pdf.name)


@router.post("/chat")
async def chat(body: ChatInput, request: Request, row=Depends(candidate)):
    rt = runtime(request)
    if not rt["store"].allowed("chat:" + row["id"]):
        raise HTTPException(429, "Bạn đã gửi nhiều câu hỏi; vui lòng chờ một phút rồi thử lại.")
    program = body.program if body.program is not None else row["context"]
    codes = {p["code"] for p in rt["knowledge"].programs}
    mentioned = [
        code for code in re.findall(r"\b[A-Z]{2,8}\d{0,3}(?:-[A-Z]+)?\b", body.message.upper()) if code in codes
    ]
    if len(set(mentioned)) == 1:
        program = mentioned[0]
    if program and program not in {p["code"] for p in rt["knowledge"].programs}:
        raise HTTPException(422, "Mã chương trình chưa có trong nguồn.")
    rt["store"].context(row["id"], program)
    started = time.perf_counter()
    if rt.get("source_error"):
        answer = {
            "response": "Nguồn tuyển sinh chưa sẵn sàng. Bạn có thể chuyển cán bộ để được hỗ trợ.",
            "kind": "error",
            "sources": [],
            "mode": "extractive",
            "tokens": 0,
            "reason": "source_unavailable",
        }
    else:
        answer = await rt["admissions"].answer(body.message, program)
    elapsed = (time.perf_counter() - started) * 1000
    answer["latency_ms"] = round(elapsed, 1)
    answer["request_id"] = secrets.token_hex(8)
    answer["program"] = program
    rt["store"].add_message(row["id"], "user", {"response": redact(body.message)})
    rt["store"].add_message(row["id"], "assistant", answer)
    rt["store"].record(answer["kind"], answer["mode"], elapsed, answer.get("tokens", 0))
    return answer


@router.post("/handover")
def handover(body: TicketInput, request: Request, row=Depends(candidate)):
    if not body.consent or not body.summary.strip():
        raise HTTPException(422, "Cần có nội dung và đồng ý chuyển trước khi tạo yêu cầu.")
    store = runtime(request)["store"]
    if not store.allowed("ticket:" + row["id"], count=10, window=3600):
        raise HTTPException(429, "Quá nhiều yêu cầu trong giờ; vui lòng chờ.")
    return safe_ticket(store.create_ticket(row["id"], body.request_key, redact(body.summary.strip()), body.reason))


@router.get("/tickets")
def tickets(request: Request, row=Depends(candidate)):
    return [safe_ticket(t) for t in runtime(request)["store"].tickets(row["id"])]


@router.get("/tickets/{ticket_id}")
def ticket(ticket_id: str, request: Request, row=Depends(candidate)):
    matches = [t for t in runtime(request)["store"].tickets(row["id"]) if t["id"] == ticket_id]
    if not matches:
        raise HTTPException(404, "Không tìm thấy yêu cầu trong phiên của bạn.")
    return safe_ticket(matches[0])


@router.post("/staff/login")
def login(body: LoginInput, request: Request, response: Response):
    rt = runtime(request)
    ip = request.client.host if request.client else "unknown"
    if not rt["store"].allowed("login:" + ip, count=5, window=60):
        raise HTTPException(429, "Vui lòng chờ một phút trước khi đăng nhập lại.")
    cfg = rt["settings"]
    if not (
        secrets.compare_digest(body.username.encode(), cfg.staff_username.encode())
        and secrets.compare_digest(body.password.encode(), cfg.staff_password.encode())
    ):
        raise HTTPException(401, "Thông tin đăng nhập không hợp lệ.")
    token = rt["store"].staff_login(body.username)
    response.set_cookie("staff", token, httponly=True, samesite="strict", secure=cfg.secure_cookies, max_age=8 * 3600)
    return {"username": body.username}


@router.post("/tickets/{ticket_id}/cancel")
def cancel_ticket(ticket_id: str, request: Request, row=Depends(candidate)):
    ticket(ticket_id, request, row)
    if not runtime(request)["store"].cancel(ticket_id, row["id"]):
        raise HTTPException(409, "Chỉ có thể hủy yêu cầu đang chờ hoặc đang xử lý.")
    return {"ok": True}


@router.get("/staff/me")
def me(user=Depends(staff)):
    return {"username": user}


@router.post("/staff/logout")
def logout(request: Request, response: Response):
    runtime(request)["store"].logout(request.cookies.get("staff"))
    response.delete_cookie("staff")
    return {"ok": True}


@router.get("/staff/tickets")
def queue(request: Request, status: str | None = None, user=Depends(staff)):
    if status and status not in ["waiting", "in_progress", "resolved", "cancelled", "rejected"]:
        raise HTTPException(422, "Trạng thái không hợp lệ.")
    return [safe_ticket(t) for t in runtime(request)["store"].tickets(status=status)]


@router.post("/staff/tickets/{ticket_id}/claim")
def claim(ticket_id: str, request: Request, user=Depends(staff)):
    if not runtime(request)["store"].claim(ticket_id, user):
        raise HTTPException(409, "Yêu cầu không còn chờ hoặc đã có người nhận.")
    return {"ok": True}


@router.post("/staff/tickets/{ticket_id}/resolve")
def resolve(ticket_id: str, body: ReplyInput, request: Request, user=Depends(staff)):
    if not body.reply.strip():
        raise HTTPException(422, "Cần nhập phản hồi trước khi đóng.")
    if not runtime(request)["store"].resolve(ticket_id, user, redact(body.reply.strip())):
        raise HTTPException(409, "Cần nhận xử lý yêu cầu trước; chỉ người nhận được đóng yêu cầu.")
    return {"ok": True}


@router.get("/staff/metrics")
def metrics(request: Request, user=Depends(staff)):
    return runtime(request)["store"].metrics()


@router.post("/staff/tickets/{ticket_id}/reject")
def reject_ticket(ticket_id: str, body: ReplyInput, request: Request, user=Depends(staff)):
    if not body.reply.strip():
        raise HTTPException(422, "Cần nhập lý do từ chối.")
    if not runtime(request)["store"].reject(ticket_id, user, redact(body.reply.strip())):
        raise HTTPException(409, "Yêu cầu đã kết thúc hoặc đang được cán bộ khác xử lý.")
    return {"ok": True}
