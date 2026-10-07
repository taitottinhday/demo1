import json
import secrets
import sqlite3
import time
from datetime import date, datetime, timedelta

from fastapi import HTTPException

from src.services.accounts import create_user, hash_password
from src.services.store import digest, ticket_event

STATUSES = ["waiting", "in_progress", "resolved", "rejected", "cancelled"]
TICKET_SELECT = (
    "SELECT t.id,t.summary,t.reason,t.status,t.reply,t.created,t.updated,t.claimed_at,t.resolved_at,"
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
        return {"items": [dict(r) for r in rows], "total": total, "page": page, "page_size": page_size}

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
            **dict(row),
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
                "SELECT u.id,u.username,u.name,u.email,u.active,u.created,COUNT(t.id) AS open_tickets"
                " FROM users u LEFT JOIN tickets t ON t.owner=u.username AND t.status='in_progress'"
                " WHERE u.role='officer' GROUP BY u.id ORDER BY u.name, u.id"
            ).fetchall()
        return [{**dict(r), "active": bool(r["active"])} for r in rows]

    def officer(self, officer_id):
        return next((o for o in self.officers() if o["id"] == officer_id), None)

    def create_officer(self, username, name, email, password):
        try:
            with self.store.connect() as db:
                officer_id = create_user(db, username, name, email, "officer", password)
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Tài khoản hoặc email đã tồn tại.") from None
        return self.officer(officer_id)

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
        return {**self.officer(officer_id), "released_tickets": released}

    def reset_officer_password(self, officer_id, password):
        with self.store.connect() as db:
            row = db.execute(
                "SELECT username FROM users WHERE id=? AND role='officer'", (officer_id,)
            ).fetchone()
            if not row:
                raise HTTPException(404, "Không tìm thấy cán bộ.")
            db.execute(
                "UPDATE users SET password_hash=? WHERE id=?",
                (hash_password(password), officer_id),
            )
            db.execute("DELETE FROM staff_sessions WHERE username=?", (row["username"],))
        return self.officer(officer_id)

    # Metrics --------------------------------------------------------------
    def metrics(self, date_from=None, date_to=None, stale_hours=24):
        start = day_start(date_from) if date_from else 0
        end = day_start(date_to + timedelta(days=1)) if date_to else time.time() + 1
        span = (start, end)
        now = time.time()
        with self.store.connect() as db:
            by_status = dict.fromkeys(STATUSES, 0)
            for status, count in db.execute(
                "SELECT status,COUNT(*) FROM tickets WHERE created>=? AND created<? GROUP BY status", span
            ):
                by_status[status] = count
            avg_wait = db.execute(
                "SELECT AVG(claimed_at-created) FROM tickets WHERE claimed_at IS NOT NULL AND created>=? AND created<?",
                span,
            ).fetchone()[0]
            avg_resolve = db.execute(
                "SELECT AVG(resolved_at-claimed_at) FROM tickets WHERE status='resolved'"
                " AND claimed_at IS NOT NULL AND resolved_at IS NOT NULL AND created>=? AND created<?",
                span,
            ).fetchone()[0]
            stale = db.execute(
                TICKET_SELECT + " WHERE t.status='waiting' AND t.created<? ORDER BY t.created",
                (now - stale_hours * 3600,),
            ).fetchall()
            chats = db.execute("SELECT COUNT(*) FROM events WHERE created>=? AND created<?", span).fetchone()[0]
            answered = db.execute(
                "SELECT COUNT(*) FROM events WHERE kind='answered' AND created>=? AND created<?", span
            ).fetchone()[0]
        closed = by_status["resolved"] + by_status["rejected"]
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
            # chat_logs does not exist yet: the direct-answer rate comes from per-chat outcome events.
            "direct_answer_rate": round(answered / chats, 4) if chats else None,
            # Tickets can be opened without chatting, so tickets/chats is not a rate; null until chat_logs exists.
            "handover_rate": None,
            "rates_source": "events",
        }


def day_start(value: date):
    return datetime(value.year, value.month, value.day).timestamp()
