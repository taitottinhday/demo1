import asyncio
from datetime import date
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, field_validator

from src.services.accounts import authenticate
from src.services.admin import AdminStore
from src.services.admissions import redact
from src.services.email import EmailDeliveryError

router = APIRouter(prefix="/admin")


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class ReassignInput(BaseModel):
    to_officer_id: int | None
    note: str = Field(default="", max_length=500)


class OfficerInput(BaseModel):
    username: str = Field(pattern=r"^[a-zA-Z0-9_.-]{3,40}$")
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str | None = Field(default=None, min_length=8, max_length=200)

    @field_validator("name")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("Cần nhập tên.")
        return value.strip()


class OfficerPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    active: bool | None = None


class OfficerPasswordInput(BaseModel):
    password: str = Field(min_length=8, max_length=200)


def runtime(request: Request):
    return request.app.state.runtime


def admins(request: Request):
    return AdminStore(runtime(request)["store"])


def admin(request: Request):
    user = admins(request).user(request.cookies.get("admin"))
    if user:
        return user
    if runtime(request)["store"].staff_user(request.cookies.get("staff")):
        raise HTTPException(403, "Chỉ quản trị viên được truy cập.")
    raise HTTPException(401, "Bạn cần đăng nhập quản trị.")


@router.post("/login")
def login(body: LoginInput, request: Request, response: Response):
    rt = runtime(request)
    ip = request.client.host if request.client else "unknown"
    if not rt["store"].allowed("admin-login:" + ip, count=5, window=60):
        raise HTTPException(429, "Vui lòng chờ một phút trước khi đăng nhập lại.")
    if not authenticate(rt["store"], body.username, body.password, "admin"):
        raise HTTPException(401, "Thông tin đăng nhập không hợp lệ.")
    token = admins(request).login(body.username)
    response.set_cookie(
        "admin", token, httponly=True, samesite="strict", secure=rt["settings"].secure_cookies, max_age=8 * 3600
    )
    return {"username": body.username}


@router.post("/logout")
def logout(request: Request, response: Response):
    admins(request).logout(request.cookies.get("admin"))
    response.delete_cookie("admin")
    return {"ok": True}


@router.get("/me")
def me(user=Depends(admin)):
    return {"username": user}


@router.get("/tickets")
def tickets(
    request: Request,
    status: Literal["waiting", "in_progress", "resolved", "rejected", "cancelled"] | None = None,
    officer_id: int | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user=Depends(admin),
):
    return admins(request).tickets(status, officer_id, page, page_size)


@router.get("/tickets/{ticket_id}")
def ticket(ticket_id: str, request: Request, user=Depends(admin)):
    return admins(request).ticket(ticket_id)


@router.get("/tickets/{ticket_id}/history")
def history(ticket_id: str, request: Request, user=Depends(admin)):
    return admins(request).history(ticket_id)


@router.post("/tickets/{ticket_id}/reassign")
def reassign(ticket_id: str, body: ReassignInput, request: Request, user=Depends(admin)):
    return admins(request).reassign(ticket_id, body.to_officer_id, redact(body.note.strip()), user)


@router.get("/officers")
def officers(request: Request, user=Depends(admin)):
    return admins(request).officers()


@router.post("/officers", status_code=201)
async def create_officer(body: OfficerInput, request: Request, user=Depends(admin)):
    rt = runtime(request)
    mailer = rt.get("mailer")
    if (not mailer or not mailer.configured) and rt["settings"].app_env != "test":
        raise HTTPException(503, "SMTP chưa được cấu hình để gửi thư mời cán bộ.")
    officer, token = admins(request).create_officer(
        body.username,
        body.name,
        body.email.lower(),
        body.password,
        rt["settings"].staff_invite_hours,
    )
    if not mailer or not mailer.configured:
        return {**officer, "invite_sent": False}
    try:
        await send_staff_invite(rt, officer, token)
    except HTTPException:
        admins(request).remove_officer(officer["id"])
        raise
    return {**officer, "invite_sent": True}


@router.patch("/officers/{officer_id}")
def update_officer(officer_id: int, body: OfficerPatch, request: Request, user=Depends(admin)):
    if body.name is None and body.active is None:
        raise HTTPException(422, "Cần gửi tên hoặc trạng thái hoạt động.")
    name = body.name.strip() if body.name is not None else None
    if name == "":
        raise HTTPException(422, "Cần nhập tên.")
    return admins(request).update_officer(officer_id, name, body.active, user)


@router.post("/officers/{officer_id}/password")
def reset_officer_password(
    officer_id: int, body: OfficerPasswordInput, request: Request, user=Depends(admin)
):
    return admins(request).reset_officer_password(officer_id, body.password)


@router.post("/officers/{officer_id}/invite")
async def resend_officer_invite(officer_id: int, request: Request, user=Depends(admin)):
    rt = runtime(request)
    mailer = rt.get("mailer")
    if not mailer or not mailer.configured:
        raise HTTPException(503, "SMTP chưa được cấu hình để gửi thư mời cán bộ.")
    officer, token = admins(request).resend_officer_invite(officer_id, rt["settings"].staff_invite_hours)
    await send_staff_invite(rt, officer, token)
    return {**officer, "invite_sent": True}


@router.get("/metrics")
def metrics(
    request: Request,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    user=Depends(admin),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Ngày bắt đầu phải trước ngày kết thúc.")
    hours = runtime(request)["settings"].admin_stale_hours
    return admins(request).metrics(date_from, date_to, hours)


async def send_staff_invite(rt, officer, token):
    activate_url = (
        rt["settings"].public_base_url.rstrip("/")
        + "/staff/activate?token="
        + quote(token, safe="")
    )
    try:
        await asyncio.to_thread(
            rt["mailer"].send_staff_invite,
            officer["email"],
            officer["name"],
            officer["username"],
            activate_url,
            rt["settings"].staff_invite_hours,
        )
    except EmailDeliveryError as exc:
        raise HTTPException(503, "Không thể gửi thư mời cán bộ. Kiểm tra cấu hình SMTP rồi thử lại.") from exc
