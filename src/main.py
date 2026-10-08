import asyncio
import logging
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api.admin import router as admin_router
from src.api.routes import router
from src.config import get_settings
from src.services.accounts import seed_accounts
from src.services.admissions import Admissions
from src.services.email import SmtpMailer
from src.services.knowledge import Knowledge
from src.services.store import Store

ROOT = Path(__file__).resolve().parent.parent

# Some Windows Python installations do not register JavaScript MIME types.
# With nosniff enabled, browsers then refuse to execute /assets/*.js and all
# chat buttons appear inert.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")


def create_app(settings=None):
    cfg = settings or get_settings()
    allowed_origins = {
        item.strip().rstrip("/")
        for item in cfg.cors_origins.split(",")
        if item.strip()
    }
    smtp_ready = bool(cfg.smtp_host and cfg.smtp_user and cfg.smtp_password and cfg.smtp_from)
    resend_ready = bool(cfg.resend_api_key and (cfg.resend_from or cfg.smtp_from))
    public_url = urlparse(cfg.public_base_url)
    sender = cfg.resend_from or cfg.smtp_from
    sender_valid = bool(sender and "@" in sender and "." in sender.rsplit("@", 1)[-1])
    if cfg.resend_api_key and not sender_valid:
        raise ValueError("RESEND_FROM phải là địa chỉ email thuộc domain đã xác minh trên Resend.")
    if cfg.app_env == "production" and (public_url.scheme != "https" or not public_url.netloc):
        raise ValueError("PUBLIC_BASE_URL trên production phải là URL HTTPS hợp lệ.")
    if cfg.app_env == "production" and (
        cfg.staff_password == "Demo@2026!"
        or len(cfg.staff_password) < 12
        or not cfg.secure_cookies
        or len(cfg.auth_secret) < 32
        or not (smtp_ready or resend_ready)
    ):
        raise ValueError("Production cần mật khẩu cán bộ riêng ≥12 ký tự, SECURE_COOKIES=true, HTTPS và email provider hợp lệ.")
    if cfg.app_env == "production" and (cfg.admin_password == "Admin@2026!" or len(cfg.admin_password) < 12):
        raise ValueError("Production cần ADMIN_PASSWORD riêng ≥12 ký tự.")

    @asynccontextmanager
    async def lifespan(app):
        data_dir = Path(cfg.mvp_data_dir)
        if not data_dir.is_absolute():
            data_dir = ROOT / data_dir
        store = Store(data_dir / "mvp.db")
        seed_accounts(store, cfg)
        knowledge = Knowledge(data_dir)
        source_error = None
        try:
            await asyncio.to_thread(knowledge.ingest)
        except Exception as exc:
            source_error = str(exc)
            logging.warning("Nguồn chưa sẵn sàng: %s", type(exc).__name__)
        app.state.runtime = {
            "settings": cfg,
            "store": store,
            "knowledge": knowledge,
            "admissions": Admissions(knowledge, store, cfg),
            "mailer": SmtpMailer(cfg),
            "source_error": source_error,
        }
        store.purge(cfg.session_hours)

        async def cleanup():
            while True:
                await asyncio.sleep(3600)
                await asyncio.to_thread(store.purge, cfg.session_hours)

        task = asyncio.create_task(cleanup())
        yield
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    app = FastAPI(title="Trợ lý tuyển sinh X — HUST 2026", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def structured_validation_error(request: Request, exc: RequestValidationError):
        labels = {
            "email": "Email",
            "password": "Mật khẩu",
            "code": "Mã xác nhận",
            "name": "Họ và tên",
            "username": "Tài khoản",
            "token": "Liên kết bảo mật",
            "password-confirm": "Nhập lại mật khẩu",
        }
        fields = {}
        for error in exc.errors():
            loc = error.get("loc") or ()
            field = str(loc[-1]) if loc else "form"
            if field in fields:
                continue
            error_type = error.get("type", "")
            label = labels.get(field, "Thông tin")
            if error_type == "missing":
                message = f"{label} là bắt buộc."
            elif field == "email":
                message = "Email không đúng định dạng."
            elif field == "code":
                message = "Mã xác nhận phải gồm đúng 6 chữ số."
            elif field == "password":
                message = "Mật khẩu phải có ít nhất 10 ký tự và không vượt quá 200 ký tự."
            elif error_type in {"string_too_short", "too_short"}:
                message = f"{label} chưa đủ độ dài tối thiểu."
            elif error_type in {"string_too_long", "too_long"}:
                message = f"{label} vượt quá độ dài cho phép."
            elif error_type in {"string_pattern_mismatch", "value_error"}:
                message = str(error.get("msg", "Giá trị không hợp lệ."))
                if ", " in message and message.lower().startswith(("value error", "assertion error")):
                    message = message.split(", ", 1)[1]
            else:
                message = f"{label} không hợp lệ."
            fields[field] = message
        first_field = next(iter(fields), "form")
        return JSONResponse(
            {"detail": {"message": "Dữ liệu chưa hợp lệ.", "fields": fields, "first_field": first_field}},
            status_code=422,
        )

    @app.middleware("http")
    async def safeguards(request: Request, call_next):
        if request.method in {"POST", "PUT", "DELETE", "PATCH"}:
            origin = request.headers.get("origin")
            normalized_origin = origin.rstrip("/") if origin else ""
            same_host = origin and urlparse(origin).netloc == request.headers.get("host")
            if origin and not same_host and normalized_origin not in allowed_origins:
                return JSONResponse({"detail": "Chỉ cho phép thao tác từ cùng website."}, status_code=403)
            try:
                size = int(request.headers.get("content-length", "0"))
            except ValueError:
                return JSONResponse({"detail": "Kích thước yêu cầu không hợp lệ."}, status_code=400)
            if size > 32000:
                return JSONResponse({"detail": "Nội dung quá dài."}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.mount("/assets", StaticFiles(directory=ROOT / "src" / "web"), name="assets")

    @app.get("/")
    async def home():
        return FileResponse(ROOT / "src" / "web" / "index.html")

    @app.get("/staff")
    async def staff_page():
        return FileResponse(ROOT / "src" / "web" / "staff.html")

    @app.get("/staff/activate")
    async def staff_activate_page():
        return FileResponse(ROOT / "src" / "web" / "staff-activate.html")

    @app.get("/staff/reset")
    async def staff_reset_page():
        return FileResponse(ROOT / "src" / "web" / "staff-activate.html")

    @app.get("/account")
    async def account_page():
        return FileResponse(ROOT / "src" / "web" / "account.html")

    @app.get("/admin")
    async def admin_page():
        return FileResponse(ROOT / "src" / "web" / "admin.html")

    @app.get("/health")
    async def health():
        return {"status": "ok", "env": cfg.app_env, "source_ready": bool(app.state.runtime["knowledge"].chunks)}

    return app


app = create_app()
