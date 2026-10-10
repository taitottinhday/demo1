import time
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.services.accounts import authenticate
from src.services.admin import AdminStore
from src.services.store import Store

STAFF = {"username": "canbo", "password": "Demo@2026!"}
ADMIN = {"username": "admin", "password": "Admin@2026!"}


def store():
    return app.state.runtime["store"]


async def new_ticket(client, key):
    body = {"summary": "Cần hỏi học bổng " + key, "consent": True, "request_key": "admin-test-" + key}
    response = await client.post("/api/v1/handover", json=body)
    assert response.status_code == 200
    return response.json()["id"]


async def login_admin(client):
    assert (await client.post("/api/v1/admin/login", json=ADMIN)).status_code == 200


async def create_officer(client, username):
    body = {
        "username": username,
        "name": "Cán bộ " + username,
        "email": username + "@hust.test",
        "password": "Matkhau@123",
    }
    response = await client.post("/api/v1/admin/officers", json=body)
    assert response.status_code == 201
    return response.json()


def officer_id(username):
    with store().connect() as db:
        return db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()[0]


@pytest.mark.asyncio
async def test_admin_requires_admin_role(client):
    assert (await client.get("/api/v1/admin/tickets")).status_code == 401
    assert (await client.get("/api/v1/admin/session")).json() == {"authenticated": False, "username": None}
    assert (await client.get("/api/v1/staff/session")).json() == {"authenticated": False, "username": None}
    assert (await client.post("/api/v1/admin/login", json=STAFF)).status_code == 401
    assert (await client.post("/api/v1/staff/login", json=STAFF)).status_code == 200
    assert (await client.get("/api/v1/staff/session")).json() == {"authenticated": True, "username": "canbo"}
    assert (await client.get("/api/v1/admin/session")).json() == {"authenticated": False, "username": None}
    for path in ["/api/v1/admin/tickets", "/api/v1/admin/officers", "/api/v1/admin/metrics"]:
        assert (await client.get(path)).status_code == 403
    assert (await client.post("/api/v1/admin/tickets/TS-X/reassign", json={"to_officer_id": None})).status_code == 403
    # Admin accounts cannot use the staff queue either.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        assert (await other.post("/api/v1/staff/login", json=ADMIN)).status_code == 401
        await login_admin(other)
        assert (await other.get("/api/v1/admin/session")).json() == {"authenticated": True, "username": "admin"}
        assert (await other.get("/api/v1/staff/tickets")).status_code == 401
        assert (await other.get("/api/v1/admin/tickets")).status_code == 200
        await other.post("/api/v1/admin/logout")
        assert (await other.get("/api/v1/admin/me")).status_code == 401


@pytest.mark.asyncio
async def test_ticket_list_detail_and_staff_events(client):
    ticket_id = await new_ticket(client, "list")
    await client.post("/api/v1/staff/login", json=STAFF)
    assert (await client.post(f"/api/v1/staff/tickets/{ticket_id}/claim")).status_code == 200
    await login_admin(client)

    listing = (await client.get("/api/v1/admin/tickets", params={"status": "in_progress"})).json()
    assert listing["total"] == 1 and listing["items"][0]["officer_id"] == officer_id("canbo")
    assert (await client.get("/api/v1/admin/tickets", params={"status": "bogus"})).status_code == 422
    assert (await client.get("/api/v1/admin/tickets", params={"page_size": 0})).status_code == 422
    other = (await client.get("/api/v1/admin/tickets", params={"officer_id": 9999})).json()
    assert other["total"] == 0

    detail = (await client.get(f"/api/v1/admin/tickets/{ticket_id}")).json()
    assert detail["handover_reason"] == "user_request" and detail["claimed_at"]
    assert "session" not in detail and "request_key" not in detail
    assert (await client.get("/api/v1/admin/tickets/TS-NONE")).status_code == 404

    history = (await client.get(f"/api/v1/admin/tickets/{ticket_id}/history")).json()
    assert [e["action"] for e in history] == ["created", "claimed"]
    assert history[0]["actor_id"] is None and history[1]["to_officer_id"] == officer_id("canbo")


@pytest.mark.asyncio
async def test_reassign_rules(client):
    ticket_id = await new_ticket(client, "reassign")
    await login_admin(client)
    second = await create_officer(client, "canbo2")
    url = f"/api/v1/admin/tickets/{ticket_id}/reassign"

    assigned = await client.post(url, json={"to_officer_id": second["id"], "note": "Giao cho canbo2"})
    assert assigned.status_code == 200
    assert assigned.json()["status"] == "in_progress" and assigned.json()["officer_id"] == second["id"]
    assert (await client.post(url, json={"to_officer_id": second["id"]})).status_code == 409

    staff_id = officer_id("canbo")
    moved = (await client.post(url, json={"to_officer_id": staff_id})).json()
    assert moved["officer_id"] == staff_id and moved["claimed_at"] == assigned.json()["claimed_at"]

    back = (await client.post(url, json={"to_officer_id": None, "note": "Trả hàng chờ"})).json()
    assert back["status"] == "waiting" and back["officer_id"] is None and back["claimed_at"] is None

    assert (await client.post(url, json={"to_officer_id": 9999})).status_code == 422
    assert (await client.post(url, json={"to_officer_id": officer_id("admin")})).status_code == 422
    assert (await client.post(url, json={"note": "thiếu to_officer_id"})).status_code == 422
    assert (
        await client.post("/api/v1/admin/tickets/TS-NONE/reassign", json={"to_officer_id": None})
    ).status_code == 404

    events = (await client.get(f"/api/v1/admin/tickets/{ticket_id}/history")).json()
    reassigned = [e for e in events if e["action"] == "reassigned"]
    assert len(reassigned) == 3
    assert reassigned[0]["from_officer_id"] is None and reassigned[0]["to_officer_id"] == second["id"]
    assert reassigned[1]["from_officer_id"] == second["id"] and reassigned[1]["to_officer_id"] == staff_id
    assert reassigned[2]["to_officer_id"] is None and reassigned[2]["note"] == "Trả hàng chờ"
    assert all(e["actor_id"] == officer_id("admin") for e in reassigned)
    with store().connect() as db:
        audit = db.execute(
            "SELECT action,actor,target_type,target_id FROM admin_audit_events WHERE target_id=? ORDER BY id",
            (ticket_id,),
        ).fetchall()
    assert len(audit) == 3 and all(row[0] == "reassign" and row[1] == "admin" for row in audit)

    # Finished tickets cannot be reassigned.
    await client.post(url, json={"to_officer_id": staff_id})
    await client.post("/api/v1/staff/login", json=STAFF)
    reply = {"reply": "Đã trả lời ứng viên."}
    assert (await client.post(f"/api/v1/staff/tickets/{ticket_id}/resolve", json=reply)).status_code == 200
    assert (await client.post(url, json={"to_officer_id": second["id"]})).status_code == 409
    assert (await client.post(url, json={"to_officer_id": None})).status_code == 409


@pytest.mark.asyncio
async def test_reassign_conflict_with_stale_state(client):
    ticket_id = await new_ticket(client, "race")
    admins = AdminStore(store())
    # Admin read the ticket as waiting, then an officer claimed it before the write.
    assert store().claim(ticket_id, "canbo")
    with store().connect() as db:
        assert not admins.move(db, ticket_id, "waiting", None, None, "", "admin")
    await login_admin(client)
    detail = (await client.get(f"/api/v1/admin/tickets/{ticket_id}")).json()
    assert detail["status"] == "in_progress" and detail["officer_id"] == officer_id("canbo")
    history = (await client.get(f"/api/v1/admin/tickets/{ticket_id}/history")).json()
    assert "reassigned" not in [e["action"] for e in history]


@pytest.mark.asyncio
async def test_lock_officer_releases_tickets(client):
    held = [await new_ticket(client, "lock-1"), await new_ticket(client, "lock-2")]
    done = await new_ticket(client, "lock-3")
    await client.post("/api/v1/staff/login", json=STAFF)
    for ticket_id in [*held, done]:
        assert (await client.post(f"/api/v1/staff/tickets/{ticket_id}/claim")).status_code == 200
    reply = {"reply": "Đã trả lời ứng viên."}
    assert (await client.post(f"/api/v1/staff/tickets/{done}/resolve", json=reply)).status_code == 200

    await login_admin(client)
    staff_id = officer_id("canbo")
    officers = (await client.get("/api/v1/admin/officers")).json()
    assert next(o for o in officers if o["id"] == staff_id)["open_tickets"] == 2

    locked = (await client.patch(f"/api/v1/admin/officers/{staff_id}", json={"active": False})).json()
    assert locked["active"] is False and locked["released_tickets"] == 2 and locked["open_tickets"] == 0
    for ticket_id in held:
        detail = (await client.get(f"/api/v1/admin/tickets/{ticket_id}")).json()
        assert detail["status"] == "waiting" and detail["officer_id"] is None
        last = (await client.get(f"/api/v1/admin/tickets/{ticket_id}/history")).json()[-1]
        assert last["action"] == "reassigned" and last["from_officer_id"] == staff_id and last["to_officer_id"] is None
    assert (await client.get(f"/api/v1/admin/tickets/{done}")).json()["status"] == "resolved"

    # The locked officer is logged out and cannot log back in; reassigning to them is rejected.
    assert (await client.get("/api/v1/staff/tickets")).status_code == 401
    assert (await client.post("/api/v1/staff/login", json=STAFF)).status_code == 401
    url = f"/api/v1/admin/tickets/{held[0]}/reassign"
    assert (await client.post(url, json={"to_officer_id": staff_id})).status_code == 422

    unlocked = await client.patch(f"/api/v1/admin/officers/{staff_id}", json={"active": True, "name": "Cán bộ A"})
    assert unlocked.json()["active"] is True and unlocked.json()["name"] == "Cán bộ A"
    assert (await client.post("/api/v1/staff/login", json=STAFF)).status_code == 200
    assert (await client.patch(f"/api/v1/admin/officers/{staff_id}", json={})).status_code == 422
    assert (
        await client.patch(f"/api/v1/admin/officers/{officer_id('admin')}", json={"active": False})
    ).status_code == 404
    with store().connect() as db:
        audit = db.execute(
            "SELECT action,actor,target_id,note FROM admin_audit_events WHERE target_type='officer' AND target_id=? ORDER BY id",
            (str(staff_id),),
        ).fetchall()
    assert [row[0] for row in audit] == ["lock", "unlock"]
    assert all(row[1] == "admin" for row in audit)
    assert "hàng chờ" in audit[0][3]


@pytest.mark.asyncio
async def test_create_officer_validation(client):
    await login_admin(client)
    officer = await create_officer(client, "moi_canbo")
    assert officer["open_tickets"] == 0 and officer["active"] is True and "password_hash" not in officer
    duplicate = {"username": "moi_canbo", "name": "X", "email": "khac@hust.test", "password": "Matkhau@123"}
    assert (await client.post("/api/v1/admin/officers", json=duplicate)).status_code == 409
    weak = {"username": "yeu", "name": "X", "email": "yeu@hust.test", "password": "123"}
    assert (await client.post("/api/v1/admin/officers", json=weak)).status_code == 422
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        login = {"username": "moi_canbo", "password": "Matkhau@123"}
        assert (await other.post("/api/v1/staff/login", json=login)).status_code == 200
    with store().connect() as db:
        audit = db.execute(
            "SELECT action,actor,target_id FROM admin_audit_events WHERE action='invite' AND target_type='officer' AND target_id=?",
            (str(officer["id"]),),
        ).fetchall()
    assert audit and audit[-1][1] == "admin"


@pytest.mark.asyncio
async def test_admin_can_reset_officer_password_without_exposing_it(client):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as staff_client:
        assert (await staff_client.post("/api/v1/staff/login", json=STAFF)).status_code == 200
        await login_admin(client)
        officer = next(o for o in (await client.get("/api/v1/admin/officers")).json() if o["username"] == "canbo")
        response = await client.post(
            f"/api/v1/admin/officers/{officer['id']}/password",
            json={"password": "NewOfficer@123"},
        )
        assert response.status_code == 200
        assert "password" not in response.json() and "password_hash" not in response.json()
        assert (await staff_client.get("/api/v1/staff/tickets")).status_code == 401
        assert (await staff_client.post("/api/v1/staff/login", json=STAFF)).status_code == 401
        assert (
            await staff_client.post(
                "/api/v1/staff/login", json={"username": "canbo", "password": "NewOfficer@123"}
            )
            ).status_code == 200
    with store().connect() as db:
        audit = db.execute(
            "SELECT action,actor,target_id FROM admin_audit_events WHERE action='reset_password' AND target_id=? ORDER BY id DESC LIMIT 1",
            (str(officer["id"]),),
        ).fetchone()
    assert audit and audit[1] == "admin"


@pytest.mark.asyncio
async def test_metrics_with_sample_data(client):
    now = time.time()
    hour = 3600
    rows = [
        # id, status, owner, created, claimed_at, resolved_at
        ("TS-W-OLD", "waiting", None, now - 30 * hour, None, None),
        ("TS-W-NEW", "waiting", None, now - hour, None, None),
        ("TS-P", "in_progress", "canbo", now - 5 * hour, now - 4 * hour, None),
        ("TS-R1", "resolved", "canbo", now - 10 * hour, now - 9 * hour, now - 7 * hour),
        ("TS-R2", "resolved", "canbo", now - 10 * hour, now - 7 * hour, now - 6 * hour),
        ("TS-X", "rejected", "canbo", now - 3 * hour, None, now - 2 * hour),
    ]
    with store().connect() as db:
        for ticket_id, status, owner, created, claimed, resolved in rows:
            db.execute(
                "INSERT INTO tickets(id,session,request_key,summary,reason,status,owner,reply,created,updated,"
                "claimed_at,resolved_at) VALUES(?,?,?,?,'low_confidence',?,?,'',?,?,?,?)",
                (ticket_id, "s", ticket_id, "Mẫu", status, owner, created, created, claimed, resolved),
            )
        for kind in ["answered", "answered", "answered", "fallback"]:
            db.execute("INSERT INTO events(kind,mode,latency,tokens,created) VALUES(?,'extractive',1,0,?)", (kind, now))
    await login_admin(client)
    m = (await client.get("/api/v1/admin/metrics")).json()
    assert m["tickets_by_status"] == {"waiting": 2, "in_progress": 1, "resolved": 2, "rejected": 1, "cancelled": 0}
    assert m["avg_wait_seconds"] == pytest.approx((1 + 1 + 3) / 3 * hour, abs=1)
    assert m["avg_resolve_seconds"] == pytest.approx((2 + 1) / 2 * hour, abs=1)
    assert m["reject_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert [t["id"] for t in m["stale_waiting"]] == ["TS-W-OLD"]
    assert next(o for o in m["officer_load"] if o["name"] == "Cán bộ tuyển sinh")["open_tickets"] == 1
    assert m["direct_answer_rate"] == 0.75
    assert m["handover_rate"]["value"] is None
    assert m["handover_rate"]["numerator"] is None and m["handover_rate"]["denominator"] is None
    assert m["handover_rate"]["status"] == "Chưa đủ dữ liệu"
    assert "chưa liên kết" in m["handover_rate"]["reason"]
    handover_kpi = next(k for k in m["kpis"] if k["key"] == "handover_tickets")
    assert handover_kpi["value"] == 6 and handover_kpi["denominator"] is None
    assert all({"label", "formula", "numerator", "denominator", "time_window", "timezone", "last_updated", "source"} <= set(k) for k in m["kpis"])
    assert m["data_timezone"] == "Asia/Ho_Chi_Minh"

    today = time.strftime("%Y-%m-%d")
    assert (await client.get("/api/v1/admin/metrics", params={"from": today, "to": today})).status_code == 200
    future = (await client.get("/api/v1/admin/metrics", params={"from": "2099-01-01"})).json()
    assert sum(future["tickets_by_status"].values()) == 0 and future["reject_rate"] is None
    assert future["handover_rate"]["value"] is None and future["handover_rate"]["status"] == "Chưa đủ dữ liệu"
    assert next(k for k in future["kpis"] if k["key"] == "handover_tickets")["value"] == 0
    assert (await client.get("/api/v1/admin/metrics", params={"from": "hôm qua"})).status_code == 422
    bad_range = {"from": "2026-02-01", "to": "2026-01-01"}
    assert (await client.get("/api/v1/admin/metrics", params=bad_range)).status_code == 422


@pytest.mark.asyncio
async def test_unlinked_tickets_and_question_events_never_form_a_handover_rate(client):
    # Ho Chi Minh City uses UTC+07:00 without daylight-saving changes. Using a
    # fixed offset keeps this test portable to Windows installations without
    # an IANA timezone database (or the optional `tzdata` package).
    hcm = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")
    in_range = datetime(2026, 10, 8, 12, tzinfo=hcm).timestamp()
    outside_range = datetime(2026, 10, 7, 12, tzinfo=hcm).timestamp()
    with store().connect() as db:
        for index in range(50):
            created = in_range + index if index < 48 else outside_range + index
            ticket_id = f"TS-KPI-{index + 1:02d}"
            db.execute(
                "INSERT INTO tickets(id,session,request_key,summary,reason,status,created,updated) "
                "VALUES(?,?,?,'Ticket demo','user_request','waiting',?,?)",
                (ticket_id, f"session-{index}", ticket_id, created, created),
            )
            db.execute(
                "INSERT INTO ticket_events(ticket_id,actor,action,created) VALUES(?,'candidate','created',?)",
                (ticket_id, created),
            )
        for index in range(11):
            db.execute(
                "INSERT INTO events(kind,mode,latency,tokens,created) VALUES('answered','extractive',1,0,?)",
                (in_range + index,),
            )

    await login_admin(client)
    all_time = (await client.get("/api/v1/admin/metrics")).json()
    assert all_time["handover_rate"]["value"] is None
    assert all_time["handover_rate"]["status"] == "Chưa đủ dữ liệu"
    all_time_count = next(k for k in all_time["kpis"] if k["key"] == "handover_tickets")
    assert all_time_count["value"] == 50
    assert all_time_count["formula"] == "Số ticket được tạo trong khoảng thời gian đã chọn"

    selected = (await client.get("/api/v1/admin/metrics", params={"from": "2026-10-08", "to": "2026-10-09"})).json()
    assert selected["handover_rate"]["value"] is None
    selected_count = next(k for k in selected["kpis"] if k["key"] == "handover_tickets")
    assert selected_count["value"] == 48
    assert selected_count["time_window"] == selected["data_window"]


def test_staff_invitation_activation_lifecycle(tmp_path):
    staff_store = Store(tmp_path / "staff-invite.db")
    admins = AdminStore(staff_store)
    officer, token = admins.create_officer("invitee", "Cán bộ thử nghiệm", "invitee@example.test", None, 48)

    assert token and officer["password_status"] == "invite_sent"
    assert staff_store.activate_staff_invite(token, "InviteePass@123") == "invitee"
    assert authenticate(staff_store, "invitee", "InviteePass@123", "officer") == "invitee"
    assert admins.officer(officer["id"])["password_status"] == "ready"
    assert staff_store.activate_staff_invite(token, "AnotherPass@123") is None
