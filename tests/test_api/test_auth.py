import time

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.config import Settings
from src.main import app
from src.services.admin import AdminStore
from src.services.admissions import Admissions
from src.services.email import EmailDeliveryError, SmtpMailer
from src.services.store import Store


class FakeMailer:
    configured = True

    def __init__(self, fail=False):
        self.codes = []
        self.invites = []
        self.fail = fail

    def send_code(self, recipient, code, purpose, name=""):
        if self.fail:
            raise EmailDeliveryError("provider unavailable")
        self.codes.append({"recipient": recipient, "code": code, "purpose": purpose})

    def send_login_notice(self, *args, **kwargs):
        return None

    def send_staff_invite(self, *args, **kwargs):
        if self.fail:
            raise EmailDeliveryError("provider unavailable")
        self.invites.append((args, kwargs))


@pytest_asyncio.fixture
async def auth_client(tmp_path, knowledge):
    cfg = Settings(_env_file=None, answer_mode="extractive", app_env="test", otp_resend_seconds=10)
    store = Store(tmp_path / "auth.db")
    mailer = FakeMailer()
    app.state.runtime = {
        "settings": cfg,
        "store": store,
        "knowledge": knowledge,
        "admissions": Admissions(knowledge, store, cfg),
        "mailer": mailer,
        "source_error": None,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.mailer = mailer
        yield client


@pytest.mark.asyncio
async def test_auth_validation_is_structured_vietnamese_and_keeps_valid_data(auth_client):
    response = await auth_client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "StrongPassword@123", "name": "Người dùng"},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["first_field"] == "email"
    assert "Email" in detail["fields"]["email"]
    assert "type" not in detail["fields"]["email"]


@pytest.mark.asyncio
async def test_otp_metadata_resend_and_reuse(auth_client):
    email = "student@example.com"
    registered = await auth_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPassword@123", "name": "Sinh viên"},
    )
    assert registered.status_code == 200
    otp = registered.json()["otp"]
    assert otp["email"].startswith("st") and otp["email"].endswith("@example.com") and "*" in otp["email"]
    assert otp["expires_in"] > 0 and otp["resend_after"] == 10
    assert email not in str(otp)

    resent = await auth_client.post("/api/v1/auth/resend-code", json={"email": email, "purpose": "verify"})
    assert resent.status_code == 200 and resent.json()["otp"]["resend_after"] == 10
    code = auth_client.mailer.codes[-1]["code"]
    assert (await auth_client.post("/api/v1/auth/verify-email", json={"email": email, "code": code})).status_code == 200
    assert (await auth_client.post("/api/v1/auth/verify-email", json={"email": email, "code": code})).status_code == 422

    forgot = await auth_client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot.status_code == 200
    masked_email = forgot.json()["otp"]["email"]
    assert masked_email.startswith("st") and masked_email.endswith("@example.com") and "*" in masked_email
    reset_code = auth_client.mailer.codes[-1]["code"]
    reset = await auth_client.post(
        "/api/v1/auth/reset-password",
        json={"email": email, "code": reset_code, "password": "NewStrongPassword@123"},
    )
    assert reset.status_code == 200
    reused = await auth_client.post(
        "/api/v1/auth/reset-password",
        json={"email": email, "code": reset_code, "password": "AnotherPassword@123"},
    )
    assert reused.status_code == 422


@pytest.mark.asyncio
async def test_failed_registration_email_does_not_leave_orphan_account(auth_client):
    auth_client.mailer.fail = True
    response = await auth_client.post(
        "/api/v1/auth/register",
        json={"email": "orphan@example.com", "password": "StrongPassword@123", "name": "Không gửi được"},
    )
    assert response.status_code == 503
    assert app.state.runtime["store"].student("orphan@example.com") is None


def test_staff_invite_token_is_hashed_expiring_and_one_time(tmp_path):
    store = Store(tmp_path / "staff.db")
    admins = AdminStore(store)
    officer, token = admins.create_officer("invitee", "Cán bộ", "invitee@example.test", None, 48)
    with store.connect() as db:
        row = db.execute("SELECT token_hash,expires FROM staff_invites WHERE officer_id=?", (officer["id"],)).fetchone()
        assert row["token_hash"] != token and len(row["token_hash"]) == 64
        db.execute("UPDATE staff_invites SET expires=? WHERE officer_id=?", (time.time() - 1, officer["id"]))
    assert store.activate_staff_invite(token, "InviteePass@123") is None

    officer2, token2 = admins.create_officer("invitee2", "Cán bộ 2", "invitee2@example.test", None, 48)
    assert store.activate_staff_invite(token2, "InviteePass@123") == "invitee2"
    assert store.activate_staff_invite(token2, "AnotherPass@123") is None
    reset_officer, reset_token = admins.request_password_reset(officer2["id"], 48)
    assert reset_officer["account_status"] == "reset_requested"
    assert store.activate_staff_invite(reset_token, "ResetPass@123") == "invitee2"
    assert admins.officer(officer2["id"])["account_status"] == "activated"


def test_expired_otp_is_rejected(tmp_path):
    store = Store(tmp_path / "otp.db")
    store.student_register("otp@example.com", "StrongPassword@123", "OTP")
    code = store.issue_code("otp@example.com", "verify", "test-secret", -1)
    status, student = store.verify_code("otp@example.com", "verify", code, "test-secret", 5)
    assert status == "expired" and student is None


def test_student_staff_and_admin_sessions_expire(tmp_path):
    store = Store(tmp_path / "sessions.db")
    now = time.time()
    store.student_register("session@example.com", "StrongPassword@123", "Session")
    with store.connect() as db:
        db.execute("UPDATE students SET verified_at=? WHERE email=?", (now, "session@example.com"))
    student_token, student = store.student_login("session@example.com", "StrongPassword@123", 24)
    with store.connect() as db:
        db.execute("UPDATE student_sessions SET expires=?", (now - 1,))
    assert store.student_user(student_token) is None

    from src.services.accounts import create_user

    with store.connect() as db:
        create_user(db, "officer", "Officer", "officer@example.com", "officer", "StrongPassword@123")
        create_user(db, "admin", "Admin", "admin@example.com", "admin", "StrongPassword@123")
    staff_token = store.staff_login("officer")
    with store.connect() as db:
        db.execute("UPDATE staff_sessions SET expires=?", (now - 1,))
    assert store.staff_user(staff_token) is None
    admin_store = AdminStore(store)
    admin_token = admin_store.login("admin")
    with store.connect() as db:
        db.execute("UPDATE admin_sessions SET expires=?", (now - 1,))
    assert admin_store.user(admin_token) is None


def test_staff_email_has_two_safe_action_links(tmp_path):
    cfg = Settings(_env_file=None, smtp_host="smtp.test", smtp_user="u", smtp_password="p", smtp_from="no-reply@example.com")
    mailer = SmtpMailer(cfg)
    sent = []
    mailer._deliver = sent.append
    mailer.send_staff_invite(
        "officer@example.com",
        "Cán bộ",
        "officer",
        "https://example.com/staff/activate#token=one-time",
        48,
        "https://example.com/staff/reset#token=one-time",
    )
    message = sent[0]
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "Kích hoạt tài khoản" in html and "Đặt lại mật khẩu" in html
    assert "#token=one-time" in html and "?token=one-time" not in html
    assert "mật khẩu hiện tại" not in html.lower()
