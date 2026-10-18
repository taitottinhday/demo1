from http.cookies import SimpleCookie

from starlette.requests import Request
from starlette.responses import Response

from src.api import admin as admin_api
from src.api import routes
from src.config import Settings
from src.main import app, seed_demo_tickets
from src.services.accounts import seed_accounts
from src.services.admin import AdminStore
from src.services.store import Store


def request_with_cookie(cookie=""):
    headers = [(b"cookie", cookie.encode())] if cookie else []
    return Request({
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": headers,
        "client": ("test", 1234),
        "server": ("test", 80),
        "app": app,
    })


def response_cookies(response):
    parsed = SimpleCookie()
    for name, value in response.raw_headers:
        if name.lower() == b"set-cookie":
            parsed.load(value.decode())
    return {key: morsel.value for key, morsel in parsed.items()}


def test_public_staff_and_admin_demo_share_the_main_store(tmp_path):
    base_store = Store(tmp_path / "production" / "mvp.db")
    _, real_session = base_store.session(None, 24)
    real_ticket = base_store.create_ticket(
        real_session["id"], "real-only", "REAL-ONLY confidential record", "user_request"
    )
    demo_cfg = Settings(
        _env_file=None,
        app_env="production",
        staff_username="demo-officer",
        admin_username="demo-admin",
    )
    seed_accounts(base_store, demo_cfg)
    seed_demo_tickets(base_store, demo_cfg)
    app.state.runtime = {
        "settings": demo_cfg,
        "store": base_store,
        "demo_runtime": {"settings": demo_cfg, "store": base_store, "mailer": None},
    }

    assert routes.demo_status(request_with_cookie()) == {"enabled": True}
    staff_response = Response()
    assert routes.demo_staff_login(request_with_cookie(), staff_response)["demo"] is True
    staff_cookies = response_cookies(staff_response)
    staff_request = request_with_cookie(
        f"demo_mode={staff_cookies['demo_mode']}; staff={staff_cookies['staff']}"
    )
    assert routes.staff_session_status(staff_request) == {
        "authenticated": True,
        "username": "demo-officer",
    }
    staff_tickets = routes.queue(staff_request, user="demo-officer")
    assert len(staff_tickets) == 4
    assert sum("Câu hỏi mẫu:" in ticket["summary"] for ticket in staff_tickets) == 3

    admin_response = Response()
    assert routes.demo_admin_login(request_with_cookie(), admin_response)["demo"] is True
    admin_cookies = response_cookies(admin_response)
    admin_request = request_with_cookie(
        f"demo_mode={admin_cookies['demo_mode']}; admin={admin_cookies['admin']}"
    )
    assert admin_api.session_status(admin_request) == {
        "authenticated": True,
        "username": "demo-admin",
    }
    assert admin_api.runtime(admin_request)["store"] is base_store
    assert AdminStore(base_store).tickets()["total"] == 4
    assert base_store.ticket(real_ticket["id"])["summary"] == "REAL-ONLY confidential record"
    assert admin_api.runtime(admin_request)["mailer"] is None
