import json
import secrets
import sqlite3
import time
from datetime import UTC, date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from src.services.accounts import create_user, hash_password
from src.services.store import admin_audit, digest, ticket_event

STATUSES = ["waiting", "in_progress", "resolved", "rejected", "cancelled"]
TICKET_SELECT = (
    "SELECT t.id,t.summary,t.reason,t.status,t.reply,t.question,t.ai_answer,t.sources_json,"
    "t.created,t.updated,t.claimed_at,t.resolved_at,"
    " u.id AS officer_id, COALESCE(u.name,t.owner) AS officer_name"
    " FROM tickets t LEFT JOIN users u ON u.username=t.owner"
)


class AdminStore:
    """Admin-only queries on top of the shared Store connection."""

    def __init__(self, store):
        self.store = store

    # Sessions -------------------------------------------------------------
    def login(self, username):
        token = secrets.token_urlsafe(32)
        with self.store.connect() as db:
            db.execute("INSERT INTO admin_sessions VALUES(?,?,?)", (digest(token), username, time.time() + 8 * 3600))
        return token

    def user(self, token):
        with self.store.connect() as db:
            row = db.execute(
                "SELECT s.username FROM admin_sessions s JOIN users u ON u.username=s.username"
                " WHERE s.token=? AND s.expires>? AND u.role='admin' AND u.active=1",
                (digest(token or ""), time.time()),
            ).fetchone()
        return row[0] if row else None

    def logout(self, token):
        with self.store.connect() as db:
            db.execute("DELETE FROM admin_sessions WHERE token=?", (digest(token or ""),))

    # Tickets --------------------------------------------------------------
    def tickets(self, status=None, officer_id=None, page=1, page_size=20):
        where, args = " WHERE 1=1", []
        if status:
            where += " AND t.status=?"
            args.append(status)
        if officer_id is not None:
            where += " AND u.id=?"
            args.append(officer_id)
        with self.store.connect() as db:
            total = db.execute(
                "SELECT COUNT(*) FROM tickets t LEFT JOIN users u ON u.username=t.owner" + where, args
            ).fetchone()[0]
            rows = db.execute(
                TICKET_SELECT + where + " ORDER BY t.created DESC LIMIT ? OFFSET ?",
                [*args, page_size, (page - 1) * page_size],
            ).fetchall()
        return {"items": [self._public_ticket_row(r) for r in rows], "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def _public_ticket_row(row):
        value = dict(row)
        value.pop("sources_json", None)
        return value

    def ticket(self, ticket_id):
        with self.store.connect() as db:
            row = db.execute(TICKET_SELECT + " WHERE t.id=?", (ticket_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Không tìm thấy ticket.")
            session = db.execute("SELECT session FROM tickets WHERE id=?", (ticket_id,)).fetchone()[0]
            # Only the conversation that led to the handover, not later chats in the same session.
            messages = db.execute(
                "SELECT role,payload,created FROM messages WHERE session=? AND created<=? ORDER BY id DESC LIMIT 20",
                (session, row["created"]),
            ).fetchall()
        conversation = []
        if row["question"] or row["ai_answer"] or row["sources_json"] not in (None, "", "[]"):
            conversation.append({"role": "user", "text": row["question"] or row["summary"], "kind": None, "sources": [], "created": row["created"]})
            conversation.append({"role": "assistant", "text": row["ai_answer"], "kind": None, "sources": json.loads(row["sources_json"] or "[]"), "created": row["created"]})
        else:
            for m in reversed(messages):
                payload = json.loads(m["payload"])
                conversation.append(
                    {
                        "role": m["role"],
                        "text": payload.get("response", ""),
                        "kind": payload.get("kind"),
                        "sources": payload.get("sources") or [],
                        "created": m["created"],
                    }
                )
        answer = next((m for m in reversed(conversation) if m["role"] == "assistant"), None)
        return {
            **self._public_ticket_row(row),
            "handover_reason": row["reason"],
            "ai_answer": answer["text"] if answer else None,
            "ai_sources": answer["sources"] if answer else [],
            "confidence_score": None,  # Not recorded by the AI pipeline yet.
            "conversation": conversation,
        }

    def history(self, ticket_id):
        with self.store.connect() as db:
            if not db.execute("SELECT 1 FROM tickets WHERE id=?", (ticket_id,)).fetchone():
                raise HTTPException(404, "Không tìm thấy ticket.")
            rows = db.execute(
                "SELECT e.id,e.action,e.note,e.created,e.actor_id,a.name AS actor_name,a.role AS actor_role,"
                " e.from_officer_id,f.name AS from_officer_name,e.to_officer_id,o.name AS to_officer_name"
                " FROM ticket_events e LEFT JOIN users a ON a.id=e.actor_id"
                " LEFT JOIN users f ON f.id=e.from_officer_id LEFT JOIN users o ON o.id=e.to_officer_id"
                " WHERE e.ticket_id=? ORDER BY e.created, e.id",
                (ticket_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def reassign(self, ticket_id, to_officer_id, note, actor):
        with self.store.connect() as db:
            row = db.execute("SELECT status,owner FROM tickets WHERE id=?", (ticket_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Không tìm thấy ticket.")
            if row["status"] not in ["waiting", "in_progress"]:
                raise HTTPException(409, "Ticket đã kết thúc, không thể phân công lại.")
            target = None
            if to_officer_id is not None:
                found = db.execute(
                    "SELECT username FROM users WHERE id=? AND role='officer' AND active=1", (to_officer_id,)
                ).fetchone()
                if not found:
                    raise HTTPException(422, "Cán bộ nhận không tồn tại hoặc đã bị khóa.")
                target = found[0]
            if target == row["owner"]:
                raise HTTPException(409, "Ticket đã ở đúng trạng thái này.")
            if not self.move(db, ticket_id, row["status"], row["owner"], target, note, actor):
                raise HTTPException(409, "Ticket vừa được người khác thay đổi, vui lòng tải lại.")
            admin_audit(db, "reassign", actor, "ticket", ticket_id, note or "Phân công lại ticket")
        return self.ticket(ticket_id)

    def move(self, db, ticket_id, status, owner, target, note, actor):
        """Conditional update against the state the caller read; False means someone changed it first."""
        now = time.time()
        if target:
            sql = (
                "UPDATE tickets SET owner=?,status='in_progress',claimed_at=COALESCE(claimed_at,?),updated=?"
                " WHERE id=? AND status=? AND owner IS ?"
            )
            args = (target, now, now, ticket_id, status, owner)
        else:
            sql = (
                "UPDATE tickets SET owner=NULL,status='waiting',claimed_at=NULL,updated=?"
                " WHERE id=? AND status=? AND owner IS ?"
            )
            args = (now, ticket_id, status, owner)
        if db.execute(sql, args).rowcount != 1:
            return False
        ticket_event(db, ticket_id, "reassigned", actor=actor, from_owner=owner, to_owner=target, note=note or None)
        return True

    # Officers -------------------------------------------------------------
    def officers(self):
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT u.id,u.username,u.name,u.email,u.active,u.created,u.password_set_at,u.invite_sent_at,u.reset_requested_at,"
                "COUNT(t.id) AS open_tickets"
                " FROM users u LEFT JOIN tickets t ON t.owner=u.username AND t.status='in_progress'"
                " WHERE u.role='officer' GROUP BY u.id ORDER BY u.name, u.id"
            ).fetchall()
        result = []
        for row in rows:
            officer = {**dict(row), "active": bool(row["active"])}
            officer["password_status"] = "ready" if row["password_set_at"] else "invite_sent"
            officer["account_status"] = (
                "reset_requested"
                if row["reset_requested_at"] and row["password_set_at"]
                else "activated"
                if row["password_set_at"]
                else "not_activated"
            )
            result.append(officer)
        return result

    def officer(self, officer_id):
        return next((o for o in self.officers() if o["id"] == officer_id), None)

    def create_officer(self, username, name, email, password, invite_hours):
        password = password or secrets.token_urlsafe(24)
        try:
            with self.store.connect() as db:
                officer_id = create_user(db, username, name, email, "officer", password)
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Tài khoản hoặc email đã tồn tại.") from None
        token = self.store.create_staff_invite(officer_id, invite_hours, reset_requested=False)
        return self.officer(officer_id), token

    def resend_officer_invite(self, officer_id, invite_hours):
        officer = self.officer(officer_id)
        if not officer:
            raise HTTPException(404, "Không tìm thấy cán bộ.")
        if not officer["active"]:
            raise HTTPException(409, "Cán bộ đang bị khóa, không thể gửi lời mời.")
        if officer["password_status"] == "ready":
            raise HTTPException(409, "Cán bộ đã thiết lập mật khẩu. Hãy dùng chức năng đặt lại mật khẩu.")
        token = self.store.create_staff_invite(officer_id, invite_hours, reset_requested=False)
        return self.officer(officer_id), token

    def request_password_reset(self, officer_id, invite_hours):
        officer = self.officer(officer_id)
        if not officer:
            raise HTTPException(404, "Không tìm thấy cán bộ.")
        if not officer["active"]:
            raise HTTPException(409, "Cán bộ đang bị khóa, không thể gửi liên kết đặt lại.")
        if officer["password_status"] != "ready":
            raise HTTPException(409, "Cán bộ chưa kích hoạt. Hãy gửi lại email kích hoạt.")
        token = self.store.create_staff_invite(officer_id, invite_hours, reset_requested=True)
        return self.officer(officer_id), token

    def invalidate_invite_delivery(self, officer_id, token, reset_requested_at=None):
        self.store.invalidate_staff_invite(token, officer_id, reset_requested_at=reset_requested_at)

    def record_audit(self, action, actor, target_type, target_id=None, note=None):
        with self.store.connect() as db:
            admin_audit(db, action, actor, target_type, target_id, note)

    def remove_officer(self, officer_id):
        with self.store.connect() as db:
            db.execute("DELETE FROM staff_invites WHERE officer_id=?", (officer_id,))
            db.execute("DELETE FROM staff_sessions WHERE username=(SELECT username FROM users WHERE id=?)", (officer_id,))
            db.execute("DELETE FROM users WHERE id=? AND role='officer'", (officer_id,))

    def update_officer(self, officer_id, name, active, actor):
        released = 0
        with self.store.connect() as db:
            row = db.execute(
                "SELECT username,active FROM users WHERE id=? AND role='officer'", (officer_id,)
            ).fetchone()
            if not row:
                raise HTTPException(404, "Không tìm thấy cán bộ.")
            if name is not None:
                db.execute("UPDATE users SET name=? WHERE id=?", (name, officer_id))
            if active is True:
                db.execute("UPDATE users SET active=1 WHERE id=?", (officer_id,))
                if not row["active"]:
                    admin_audit(db, "unlock", actor, "officer", officer_id, "Mở khóa tài khoản cán bộ")
            if active is False and row["active"]:
                # Lock first so the officer cannot claim more while their tickets are released.
                db.execute("UPDATE users SET active=0 WHERE id=?", (officer_id,))
                db.execute("DELETE FROM staff_sessions WHERE username=?", (row["username"],))
                held = db.execute(
                    "SELECT id FROM tickets WHERE owner=? AND status='in_progress'", (row["username"],)
                ).fetchall()
                for (ticket_id,) in held:
                    if self.move(db, ticket_id, "in_progress", row["username"], None, "Khóa cán bộ", actor):
                        released += 1
                admin_audit(
                    db,
                    "lock",
                    actor,
                    "officer",
                    officer_id,
                    f"Khóa tài khoản; trả {released} ticket về hàng chờ.",
                )
        return {**self.officer(officer_id), "released_tickets": released}

    def reset_officer_password(self, officer_id, password, actor=None):
        with self.store.connect() as db:
            row = db.execute(
                "SELECT username FROM users WHERE id=? AND role='officer'", (officer_id,)
            ).fetchone()
            if not row:
                raise HTTPException(404, "Không tìm thấy cán bộ.")
            db.execute(
                "UPDATE users SET password_hash=?,password_set_at=?,invite_sent_at=NULL,reset_requested_at=NULL WHERE id=?",
                (hash_password(password), time.time(), officer_id),
            )
            db.execute("DELETE FROM staff_sessions WHERE username=?", (row["username"],))
            db.execute("UPDATE staff_invites SET used_at=? WHERE officer_id=? AND used_at IS NULL", (time.time(), officer_id))
            admin_audit(db, "reset_password", actor, "officer", officer_id, "Admin đặt lại mật khẩu cán bộ")
        return self.officer(officer_id)

    # Metrics --------------------------------------------------------------
    def metrics(self, date_from=None, date_to=None, stale_hours=24, timezone_name="Asia/Ho_Chi_Minh"):
        start = day_start(date_from, timezone_name) if date_from else 0
        end = day_start(date_to + timedelta(days=1), timezone_name) if date_to else time.time() + 1
        span = (start, end)
        now = time.time()
        with self.store.connect() as db:
            by_status = dict.fromkeys(STATUSES, 0)
            for status, count in db.execute(
                "SELECT status,COUNT(*) FROM tickets WHERE created>=? AND created<? GROUP BY status", span
            ):
                by_status[status] = count
            wait_stats = db.execute(
                "SELECT COALESCE(SUM(claimed_at-created),0),COUNT(*) FROM tickets "
                "WHERE claimed_at IS NOT NULL AND created>=? AND created<?",
                span,
            ).fetchone()
            resolve_stats = db.execute(
                "SELECT COALESCE(SUM(resolved_at-claimed_at),0),COUNT(*) FROM tickets WHERE status='resolved'"
                " AND claimed_at IS NOT NULL AND resolved_at IS NOT NULL AND created>=? AND created<?",
                span,
            ).fetchone()
            stale = db.execute(
                TICKET_SELECT + " WHERE t.status='waiting' AND t.created<? ORDER BY t.created",
                (now - stale_hours * 3600,),
            ).fetchall()
            chats = db.execute("SELECT COUNT(*) FROM events WHERE created>=? AND created<?", span).fetchone()[0]
            answered = db.execute(
                "SELECT COUNT(*) FROM events WHERE kind='answered' AND created>=? AND created<?", span
            ).fetchone()[0]
            handover_tickets = db.execute(
                "SELECT COUNT(*) FROM tickets WHERE created>=? AND created<?", span
            ).fetchone()[0]
        closed = by_status["resolved"] + by_status["rejected"]
        wait_sum, wait_count = wait_stats
        resolve_sum, resolve_count = resolve_stats
        avg_wait = wait_sum / wait_count if wait_count else None
        avg_resolve = resolve_sum / resolve_count if resolve_count else None
        window = {"from": iso_time(start, timezone_name) if start else None, "to": iso_time(end, timezone_name)}
        updated = iso_time(now, timezone_name)

        def kpi(key, label, value, numerator, denominator, formula, source, measured=True):
            return {
                "key": key,
                "label": label,
                "value": round(value, 4) if isinstance(value, float) else value,
                "numerator": numerator,
                "denominator": denominator,
                "formula": formula,
                "time_window": window,
                "timezone": timezone_name,
                "last_updated": updated,
                "source": source,
                "status": "Đã đo" if measured else "Chưa đủ dữ liệu",
            }

        source = "Dữ liệu ticket và kết quả xử lý câu hỏi đã ghi nhận"
        kpis = [
            kpi("waiting", "Ticket đang chờ", by_status["waiting"], by_status["waiting"], None, "Đếm ticket đang ở trạng thái Đang chờ", "Nhật ký ticket"),
            kpi("avg_wait", "Thời gian chờ trung bình", avg_wait, wait_sum, wait_count, "Tổng thời gian từ lúc tạo đến lúc nhận / số ticket đã được nhận", "Nhật ký ticket", bool(wait_count)),
            kpi("avg_resolve", "Thời gian xử lý trung bình", avg_resolve, resolve_sum, resolve_count, "Tổng thời gian từ lúc nhận đến lúc giải quyết / số ticket đã giải quyết", "Nhật ký ticket", bool(resolve_count)),
            kpi("reject_rate", "Tỷ lệ từ chối", by_status["rejected"] / closed if closed else None, by_status["rejected"], closed, "Ticket bị từ chối / (ticket đã giải quyết + ticket bị từ chối)", "Nhật ký ticket", bool(closed)),
            kpi("direct_answer_rate", "Tỷ lệ trả lời trực tiếp", answered / chats if chats else None, answered, chats, "Câu hỏi có câu trả lời trực tiếp / câu hỏi đã được ghi nhận", source, bool(chats)),
            kpi("handover_tickets", "Yêu cầu chuyển cán bộ", handover_tickets, handover_tickets, None, "Số ticket được tạo trong khoảng thời gian đã chọn", "Bảng tickets, lọc theo thời điểm tạo"),
        ]
        return {
            "tickets_by_status": by_status,
            "avg_wait_seconds": round(avg_wait, 1) if avg_wait is not None else None,
            "avg_resolve_seconds": round(avg_resolve, 1) if avg_resolve is not None else None,
            "reject_rate": round(by_status["rejected"] / closed, 4) if closed else None,
            "officer_load": [
                {"officer_id": o["id"], "name": o["name"], "active": o["active"], "open_tickets": o["open_tickets"]}
                for o in self.officers()
            ],
            "stale_hours": stale_hours,
            "stale_waiting": [{**dict(r), "waiting_seconds": round(now - r["created"])} for r in stale],
            "direct_answer_rate": round(answered / chats, 4) if chats else None,
            "handover_rate": {
                "value": None,
                "numerator": None,
                "denominator": None,
                "status": "Chưa đủ dữ liệu",
                "reason": "Chưa thể tính tỷ lệ: nhật ký câu hỏi chưa liên kết định danh với ticket.",
                "time_window": window,
                "timezone": timezone_name,
                "last_updated": updated,
                "formula": "Chưa thể tính đáng tin cậy vì chưa có liên kết định danh câu hỏi–ticket.",
            },
            "rates_source": "Nhật ký ticket và kết quả xử lý câu hỏi",
            "kpis": kpis,
            "data_window": window,
            "data_timezone": timezone_name,
            "data_last_updated": updated,
            "data_source": source,
        }


def zone(name):
    try:
        return ZoneInfo(name)
    except Exception:
        if name in {"Asia/Ho_Chi_Minh", "Asia/Saigon"}:
            return timezone(timedelta(hours=7), name)
        return UTC


def iso_time(value, timezone_name):
    return datetime.fromtimestamp(value, zone(timezone_name)).isoformat(timespec="seconds")


def day_start(value: date, timezone_name="Asia/Ho_Chi_Minh"):
    return datetime(value.year, value.month, value.day, tzinfo=zone(timezone_name)).timestamp()
