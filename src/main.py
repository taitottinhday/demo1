import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api.admin import router as admin_router
from src.api.routes import router
from src.config import get_settings
from src.services.accounts import seed_accounts
from src.services.admissions import Admissions
from src.services.knowledge import Knowledge
from src.services.store import Store

ROOT = Path(__file__).resolve().parent.parent


def create_app(settings=None):
    cfg = settings or get_settings()
    if cfg.app_env == "production" and (
        cfg.staff_password == "Demo@2026!" or len(cfg.staff_password) < 12 or not cfg.secure_cookies
    ):
        raise ValueError("Production cần STAFF_PASSWORD riêng ≥12 ký tự và SECURE_COOKIES=true với HTTPS.")
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

    @app.middleware("http")
    async def safeguards(request: Request, call_next):
        if request.method in {"POST", "PUT", "DELETE", "PATCH"}:
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.headers.get("host"):
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

    @app.get("/admin")
    async def admin_page():
        return FileResponse(ROOT / "src" / "web" / "admin.html")

    @app.get("/health")
    async def health():
        return {"status": "ok", "env": cfg.app_env, "source_ready": bool(app.state.runtime["knowledge"].chunks)}

    return app


app = create_app()
