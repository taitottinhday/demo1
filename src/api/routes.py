import asyncio
import logging
import re
import secrets
import time
from typing import Literal
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator

from src.services.accounts import authenticate
from src.services.admissions import redact
from src.services.email import EmailDeliveryError
from src.services.product_features import compare_programs
from src.services.store import digest

router = APIRouter()
logger = logging.getLogger(__name__)


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


class StaffActivateInput(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=10, max_length=200)


class ReplyInput(BaseModel):
    reply: str = Field(min_length=1, max_length=4000)


class FeedbackInput(BaseModel):
    rating: Literal["helpful", "incorrect"]


class ComparisonInput(BaseModel):
    codes: list[str] = Field(min_length=2, max_length=3)


class StudentRegisterInput(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=200)
    name: str = Field(default="", max_length=120)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Email không hợp lệ.")
        return value


class StudentEmailInput(BaseModel):
    email: str = Field(min_length=5, max_length=254)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Email không hợp lệ.")
        return value


class StudentVerifyInput(StudentEmailInput):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class StudentLoginInput(StudentEmailInput):
    password: str = Field(min_length=1, max_length=200)


class StudentResetInput(StudentVerifyInput):
    password: str = Field(min_length=10, max_length=200)


@router.get("/auth/google/start")
def student_google_start(request: Request):
    cfg = runtime(request)["settings"]
    redirect_uri = google_redirect_uri(request, cfg, "student")
    if not google_oauth_ready(cfg, redirect_uri):
        raise HTTPException(503, "Google sign-in is not configured for students.")
    state = secrets.token_urlsafe(32)
    params = urlencode({
        "client_id": cfg.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    })
    response = RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}", status_code=302)
    response.set_cookie(
        "student_google_state", state, httponly=True, samesite="lax", secure=cfg.secure_cookies, max_age=600
    )
    return response


@router.get("/auth/google/callback")
async def student_google_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    cfg = runtime(request)["settings"]
    redirect_uri = google_redirect_uri(request, cfg, "student")

    def fail(message: str):
        response = RedirectResponse("/account?login_error=" + message, status_code=302)
        response.delete_cookie("student_google_state")
        return response

    saved_state = request.cookies.get("student_google_state", "")
    if error or not code or not state or not secrets.compare_digest(saved_state, state):
        return fail("Google+sign-in+was+cancelled+or+could+not+be+verified.")
    if not google_oauth_ready(cfg, redirect_uri):
        return fail("Google+sign-in+is+not+configured.")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": cfg.google_client_id,
                    "client_secret": cfg.google_client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json().get("access_token")
            profile_response = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            profile_response.raise_for_status()
            profile = profile_response.json()
    except (httpx.HTTPError, ValueError):
        return fail("Google+sign-in+could+not+be+completed.+Please+try+again.")
    email = str(profile.get("email", "")).strip().lower()
    if not email or profile.get("email_verified") is not True:
        return fail("Google+did+not+return+a+verified+email+address.")
    token, student = runtime(request)["store"].student_google_login(email, str(profile.get("name", "")), cfg.session_hours)
    if not token:
        return fail("This+Google+account+cannot+access+the+student+area.")
    await send_login_notice(runtime(request), student, "Google", request.client.host if request.client else "")
    response = RedirectResponse("/", status_code=302)
    student_cookie(response, token, cfg)
    runtime(request)["store"].link_session(request.cookies.get("candidate"), student["id"])
    response.delete_cookie("student_google_state")
    return response


@router.post("/auth/register")
async def student_register(body: StudentRegisterInput, request: Request):
    rt = runtime(request)
    if not rt["mailer"].configured:
        raise HTTPException(503, "SMTP chưa được cấu hình để gửi mã xác nhận.")
    if not auth_rate_allowed(rt, "auth-register:", body.email):
        raise HTTPException(429, "Bạn đã yêu cầu quá nhiều mã. Vui lòng thử lại sau.")
    student = rt["store"].student_register(body.email, body.password, body.name.strip())
    if student is None:
        raise HTTPException(409, "Email này đã đăng ký. Hãy đăng nhập hoặc dùng Quên mật khẩu.")
    code = rt["store"].issue_code(body.email, "verify", rt["settings"].auth_secret, rt["settings"].verification_code_minutes)
    await send_student_code(rt, body.email, code, "verify", body.name.strip())
    return {"ok": True, "email": body.email, "message": "Mã xác nhận đã được gửi đến email của bạn."}


@router.post("/auth/verify-email")
def verify_student_email(body: StudentVerifyInput, request: Request):
    rt = runtime(request)
    status, student = rt["store"].verify_code(
        body.email, "verify", body.code, rt["settings"].auth_secret, rt["settings"].verification_max_attempts
    )
    if status != "ok":
        detail = {"invalid": "Mã không đúng.", "locked": "Mã đã bị khóa do thử quá nhiều lần.", "expired": "Mã đã hết hạn."}.get(status, "Mã không hợp lệ.")
        raise HTTPException(422, detail)
    return {"ok": True, "student": public_student(student)}


@router.post("/auth/resend-code")
async def resend_student_code(body: StudentEmailInput, request: Request):
    rt = runtime(request)
    if not auth_rate_allowed(rt, "auth-resend:", body.email):
        raise HTTPException(429, "Bạn đã yêu cầu quá nhiều mã. Vui lòng thử lại sau.")
    student = rt["store"].student(body.email)
    if student and not student["verified_at"]:
        if not rt["mailer"].configured:
            raise HTTPException(503, "SMTP chưa được cấu hình để gửi mã xác nhận.")
        code = rt["store"].issue_code(body.email, "verify", rt["settings"].auth_secret, rt["settings"].verification_code_minutes)
        await send_student_code(rt, body.email, code, "verify", student["display_name"])
    return {"ok": True, "message": "Nếu email có tài khoản chưa xác nhận, mã mới đã được gửi."}


@router.post("/auth/login")
async def student_login(body: StudentLoginInput, request: Request, response: Response):
    rt = runtime(request)
    token, result = rt["store"].student_login(body.email, body.password, rt["settings"].session_hours)
    if result == "not_verified":
        raise HTTPException(403, "Email chưa được xác nhận. Hãy nhập mã trong email trước.")
    if result == "invalid" or not token:
        raise HTTPException(401, "Email hoặc mật khẩu không đúng.")
    student_cookie(response, token, rt["settings"])
    rt["store"].link_session(request.cookies.get("candidate"), result["id"])
    await send_login_notice(rt, result, "Email/mật khẩu", request.client.host if request.client else "")
    return {"ok": True, "student": public_student(result)}


@router.get("/auth/me")
def student_me(request: Request):
    student = runtime(request)["store"].student_user(request.cookies.get("student"))
    return {"authenticated": bool(student), "student": public_student(student) if student else None}


@router.post("/auth/logout")
def student_logout(request: Request, response: Response):
    runtime(request)["store"].student_logout(request.cookies.get("student"))
    response.delete_cookie("student")
    response.delete_cookie("candidate")
    return {"ok": True}


@router.post("/auth/forgot-password")
async def forgot_student_password(body: StudentEmailInput, request: Request):
    rt = runtime(request)
    if not auth_rate_allowed(rt, "auth-forgot:", body.email):
        raise HTTPException(429, "Bạn đã yêu cầu quá nhiều mã. Vui lòng thử lại sau.")
    student = rt["store"].student(body.email)
    if student and student["verified_at"]:
        if not rt["mailer"].configured:
            raise HTTPException(503, "SMTP chưa được cấu hình để gửi mã đặt lại mật khẩu.")
        code = rt["store"].issue_code(body.email, "reset", rt["settings"].auth_secret, rt["settings"].verification_code_minutes)
        await send_student_code(rt, body.email, code, "reset", student["display_name"])
    return {"ok": True, "message": "Nếu email đã đăng ký, mã đặt lại mật khẩu đã được gửi."}


@router.post("/auth/reset-password")
def reset_student_password(body: StudentResetInput, request: Request):
    rt = runtime(request)
    status, student = rt["store"].verify_code(
        body.email, "reset", body.code, rt["settings"].auth_secret, rt["settings"].verification_max_attempts
    )
    if status != "ok":
        detail = {"invalid": "Mã không đúng.", "locked": "Mã đã bị khóa do thử quá nhiều lần.", "expired": "Mã đã hết hạn."}.get(status, "Mã không hợp lệ.")
        raise HTTPException(422, detail)
    rt["store"].reset_password(body.email, body.password)
    return {"ok": True, "message": "Mật khẩu đã được cập nhật. Bạn có thể đăng nhập."}


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
    student = rt["store"].student_user(request.cookies.get("student"))
    token, row = rt["store"].session(
        request.cookies.get("candidate"), rt["settings"].session_hours, student["id"] if student else None
    )
    response.set_cookie(
        "candidate",
        token,
        httponly=True,
        samesite="strict",
        secure=rt["settings"].secure_cookies,
        max_age=rt["settings"].session_hours * 3600,
    )
    return row


def public_student(student):
    return {"id": student["id"], "email": student["email"], "name": student["display_name"], "verified": bool(student["verified_at"])}


def student_cookie(response: Response, token: str, settings) -> None:
    response.set_cookie(
        "student", token, httponly=True, samesite="strict", secure=settings.secure_cookies,
        max_age=settings.session_hours * 3600,
    )


async def send_student_code(rt, email, code, purpose, name=""):
    try:
        await asyncio.to_thread(rt["mailer"].send_code, email, code, purpose, name)
    except EmailDeliveryError as exc:
        raise HTTPException(503, "Không thể gửi email lúc này. Kiểm tra cấu hình SMTP rồi thử lại.") from exc


async def send_login_notice(rt, student, method, ip=""):
    """Send a best-effort security alert without blocking successful login."""
    try:
        await asyncio.to_thread(
            rt["mailer"].send_login_notice,
            student["email"],
            student.get("display_name", ""),
            method,
            ip,
        )
    except EmailDeliveryError:
        logger.warning("Login notification email failed for student %s", digest(student["email"]))


def auth_rate_allowed(rt, prefix, email):
    """Use a forgiving limit locally while keeping production protection strict."""
    if rt["settings"].app_env == "development":
        return rt["store"].allowed(prefix + digest(email), count=10, window=600)
    return rt["store"].allowed(prefix + digest(email), count=3, window=3600)


_SAFE_TICKET_FIELDS = {
    "id",
    "summary",
    "reason",
    "status",
    "owner",
    "reply",
    "created",
    "updated",
}
_REDACTED_TICKET_FIELDS = {"summary", "reason", "reply"}


def safe_ticket(ticket):
    """Return only the fields needed by the candidate/staff UIs.

    This is intentionally an allowlist rather than a blacklist: internal
    fields such as session identifiers, request keys, tokens, or future
    columns must never become API data accidentally. Text is redacted again
    at this boundary so legacy rows are protected too.
    """
    safe = {}
    for key in _SAFE_TICKET_FIELDS:
        if key not in ticket:
            continue
        value = ticket[key]
        safe[key] = redact(str(value)) if key in _REDACTED_TICKET_FIELDS and value else value
    return safe


def safe_ticket_detail(detail):
    """Expose only the consented handover content and safe ticket history."""
    ticket = safe_ticket(detail["ticket"])
    return {
        **ticket,
        # The current handover contract stores the candidate-approved text in
        # summary. Do not read the whole session because it may contain
        # unrelated messages that the candidate did not consent to share.
        "shared_content": ticket["summary"],
        "context_available": False,
        "events": [
            {
                "actor": event.get("actor"),
                "action": event.get("action"),
                "created": event.get("created"),
            }
            for event in detail["events"]
        ],
    }


def google_allowlisted(email: str, settings) -> bool:
    """Require an explicit email or domain allow-list for staff access."""
    email = email.strip().lower()
    emails = {item.strip().lower() for item in settings.google_allowed_emails.split(",") if item.strip()}
    domains = {item.strip().lower().lstrip("@") for item in settings.google_allowed_email_domains.split(",") if item.strip()}
    return email in emails or ("@" in email and email.rsplit("@", 1)[1] in domains)


def google_ready(settings) -> bool:
    return bool(
        settings.google_client_id
        and settings.google_client_secret
        and settings.google_redirect_uri
        and (settings.google_allowed_emails.strip() or settings.google_allowed_email_domains.strip())
    )


def google_oauth_ready(settings, redirect_uri: str) -> bool:
    return bool(settings.google_client_id and settings.google_client_secret and redirect_uri)


def google_redirect_uri(request: Request, settings, audience: str) -> str:
    paths = {
        "staff": "/api/v1/staff/google/callback",
        "student": "/api/v1/auth/google/callback",
    }
    if settings.app_env == "development":
        return f"{request.url.scheme}://{request.headers.get('host')}{paths[audience]}"
    return settings.google_redirect_uri if audience == "staff" else settings.google_student_redirect_uri


def staff_cookie(response: Response, token: str, settings) -> None:
    response.set_cookie(
        "staff", token, httponly=True, samesite="strict", secure=settings.secure_cookies, max_age=8 * 3600
    )


def staff(request: Request):
    user = runtime(request)["store"].staff_user(request.cookies.get("staff"))
    if not user:
        raise HTTPException(401, "Bạn cần đăng nhập cán bộ.")
    return user


@router.post("/answers/{request_id}/feedback")
def answer_feedback(request_id: str, body: FeedbackInput, request: Request, row=Depends(candidate)):
    rt = runtime(request)
    student = rt["store"].student_user(request.cookies.get("student"))
    if not rt["store"].feedback(row["id"], request_id, body.rating, student["id"] if student else None):
        raise HTTPException(404, "Không tìm thấy câu trả lời trong phiên của bạn.")
    return {"rating": body.rating}


@router.get("/session")
def session(request: Request, row=Depends(candidate)):
    rt = runtime(request)
    student = rt["store"].student_user(request.cookies.get("student"))
    return {
        "messages": rt["store"].student_messages(student["id"]) if student else rt["store"].messages(row["id"]),
        "program": row["context"],
        "tickets": [safe_ticket(t) for t in rt["store"].tickets(row["id"])],
        "student": public_student(student) if student else None,
    }


@router.delete("/session/messages")
def clear(request: Request, row=Depends(candidate)):
    rt = runtime(request)
    student = rt["store"].student_user(request.cookies.get("student"))
    if student:
        rt["store"].clear_student(student["id"], row["id"])
    else:
        rt["store"].clear(row["id"])
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
    if not authenticate(rt["store"], body.username, body.password, "officer"):
        raise HTTPException(401, "Thông tin đăng nhập không hợp lệ.")
    token = rt["store"].staff_login(body.username)
    staff_cookie(response, token, cfg)
    return {"username": body.username}


@router.post("/staff/activate")
def activate_staff(body: StaffActivateInput, request: Request):
    rt = runtime(request)
    ip = request.client.host if request.client else "unknown"
    if not rt["store"].allowed("staff-activate:" + ip, count=10, window=600):
        raise HTTPException(429, "Bạn đã thử quá nhiều lần. Vui lòng thử lại sau.")
    username = rt["store"].activate_staff_invite(body.token, body.password)
    if not username:
        raise HTTPException(422, "Liên kết không hợp lệ, đã hết hạn hoặc đã được sử dụng.")
    return {"ok": True, "username": username, "message": "Mật khẩu đã được thiết lập. Bạn có thể đăng nhập."}


@router.post("/tickets/{ticket_id}/cancel")
def cancel_ticket(ticket_id: str, request: Request, row=Depends(candidate)):
    ticket(ticket_id, request, row)
    if not runtime(request)["store"].cancel(ticket_id, row["id"]):
        raise HTTPException(409, "Chỉ có thể hủy yêu cầu đang chờ hoặc đang xử lý.")
    return {"ok": True}


@router.get("/staff/google/start")
def google_start(request: Request):
    """Start Google Authorization Code OAuth with a short-lived CSRF state."""
    cfg = runtime(request)["settings"]
    redirect_uri = google_redirect_uri(request, cfg, "staff")
    if not google_oauth_ready(cfg, redirect_uri) or not (cfg.google_allowed_emails.strip() or cfg.google_allowed_email_domains.strip()):
        raise HTTPException(503, "Google sign-in is not configured. Contact an administrator.")
    state = secrets.token_urlsafe(32)
    params = urlencode({
        "client_id": cfg.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    })
    response = RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}", status_code=302)
    response.set_cookie(
        "google_oauth_state", state, httponly=True, samesite="lax", secure=cfg.secure_cookies, max_age=600
    )
    return response


@router.get("/staff/google/callback")
async def google_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    """Exchange the Google code, check the allow-list, then create a staff session."""
    cfg = runtime(request)["settings"]
    redirect_uri = google_redirect_uri(request, cfg, "staff")

    def fail(message: str):
        response = RedirectResponse("/staff?login_error=" + message, status_code=302)
        response.delete_cookie("google_oauth_state")
        return response

    saved_state = request.cookies.get("google_oauth_state", "")
    if error or not code or not state or not secrets.compare_digest(saved_state, state):
        return fail("Google+sign-in+was+cancelled+or+could+not+be+verified.")
    if not google_oauth_ready(cfg, redirect_uri) or not (cfg.google_allowed_emails.strip() or cfg.google_allowed_email_domains.strip()):
        return fail("Google+sign-in+is+not+configured.")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": cfg.google_client_id,
                    "client_secret": cfg.google_client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json().get("access_token")
            profile_response = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            profile_response.raise_for_status()
            profile = profile_response.json()
    except (httpx.HTTPError, ValueError):
        return fail("Google+sign-in+could+not+be+completed.+Please+try+again.")
    email = str(profile.get("email", "")).strip().lower()
    if not email or profile.get("email_verified") is not True or not google_allowlisted(email, cfg):
        return fail("This+Google+account+is+not+authorised+for+staff+access.")
    response = RedirectResponse("/staff", status_code=302)
    staff_cookie(response, runtime(request)["store"].staff_login(email), cfg)
    response.delete_cookie("google_oauth_state")
    return response


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


@router.get("/staff/tickets/{ticket_id}")
def staff_ticket(ticket_id: str, request: Request, user=Depends(staff)):
    detail = runtime(request)["store"].ticket_detail(ticket_id)
    if not detail:
        raise HTTPException(404, "Không tìm thấy yêu cầu.")
    return safe_ticket_detail(detail)


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
