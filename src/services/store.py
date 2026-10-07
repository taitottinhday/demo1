import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, context TEXT NOT NULL DEFAULT '', updated REAL NOT NULL,
                    student_id TEXT);
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY, session TEXT NOT NULL, role TEXT NOT NULL,
                    payload TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS tickets (
                    id TEXT PRIMARY KEY, session TEXT NOT NULL, request_key TEXT NOT NULL,
                    summary TEXT NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL,
                    owner TEXT, reply TEXT NOT NULL DEFAULT '', created REAL NOT NULL,
                    updated REAL NOT NULL, UNIQUE(session, request_key));
                CREATE TABLE IF NOT EXISTS ticket_events (
                    id INTEGER PRIMARY KEY, ticket_id TEXT NOT NULL, actor TEXT NOT NULL,
                    action TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS staff_sessions (
                    token TEXT PRIMARY KEY, username TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, kind TEXT NOT NULL, mode TEXT NOT NULL,
                    latency REAL NOT NULL, tokens INTEGER NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS budgets (day TEXT PRIMARY KEY, calls INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS limits (
                    key TEXT PRIMARY KEY, start REAL NOT NULL, count INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS students (
                    id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL DEFAULT '',
                    password_hash TEXT NOT NULL, verified_at REAL, disabled INTEGER NOT NULL DEFAULT 0,
                    created REAL NOT NULL, updated REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS verification_codes (
                    id INTEGER PRIMARY KEY, email TEXT NOT NULL, student_id TEXT, purpose TEXT NOT NULL,
                    code_hash TEXT NOT NULL, expires REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                    used_at REAL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS student_sessions (
                    token TEXT PRIMARY KEY, student_id TEXT NOT NULL, expires REAL NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL, role TEXT NOT NULL CHECK (role IN ('officer','admin')),
                    active INTEGER NOT NULL DEFAULT 1, password_hash TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    token TEXT PRIMARY KEY, username TEXT NOT NULL, expires REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_events_ticket ON ticket_events(ticket_id);
                CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
                CREATE INDEX IF NOT EXISTS idx_tickets_owner ON tickets(owner);
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(sessions)").fetchall()}
            if "student_id" not in columns:
                db.execute("ALTER TABLE sessions ADD COLUMN student_id TEXT")
            columns = {row[1] for row in db.execute("PRAGMA table_info(tickets)").fetchall()}
            for column in ["claimed_at", "resolved_at"]:
                if column not in columns:
                    db.execute(f"ALTER TABLE tickets ADD COLUMN {column} REAL")
            event_columns = {row[1] for row in db.execute("PRAGMA table_info(ticket_events)").fetchall()}
            for column, definition in {
                "actor_id": "INTEGER REFERENCES users(id)",
                "from_officer_id": "INTEGER REFERENCES users(id)",
                "to_officer_id": "INTEGER REFERENCES users(id)",
                "note": "TEXT",
            }.items():
                if column not in event_columns:
                    db.execute(f"ALTER TABLE ticket_events ADD COLUMN {column} {definition}")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def session(self, token, hours, student_id=None):
        with self.connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (digest(token),)).fetchone() if token else None
            if row and row["updated"] > time.time() - hours * 3600:
                # Never reuse a session belonging to another account (or an
                # authenticated session for anonymous browsing).
                if (row["student_id"] is not None and row["student_id"] != student_id) or (
                    student_id is None and row["student_id"] is not None
                ):
                    row = None
                elif student_id and not row["student_id"]:
                    now = time.time()
                    db.execute("UPDATE sessions SET updated=?, student_id=? WHERE id=?", (now, student_id, row["id"]))
                    row = dict(row)
                    row["updated"] = now
                    row["student_id"] = student_id
                    return token, row
                else:
                    db.execute("UPDATE sessions SET updated=? WHERE id=?", (time.time(), row["id"]))
                if row:
                    return token, dict(row)
            token = secrets.token_urlsafe(32)
            row = {"id": digest(token), "context": "", "updated": time.time(), "student_id": student_id}
            db.execute("INSERT INTO sessions(id, updated, student_id) VALUES(?,?,?)", (row["id"], row["updated"], student_id))
            return token, row

    @staticmethod
    def _password_hash(password):
        salt = secrets.token_bytes(16)
        value = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
        return f"scrypt$16384$8$1${salt.hex()}${value.hex()}"

    @staticmethod
    def _password_matches(password, encoded):
        try:
            scheme, n, r, p, salt_hex, value_hex = encoded.split("$")
            if scheme != "scrypt":
                return False
            value = hashlib.scrypt(
                password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p), dklen=len(bytes.fromhex(value_hex))
            )
            return hmac.compare_digest(value.hex(), value_hex)
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _code_hash(email, purpose, code, secret):
        return hmac.new(
            (secret or "development-auth-secret").encode(),
            f"{email}|{purpose}|{code}".encode(),
            hashlib.sha256,
        ).hexdigest()

    def student_register(self, email, password, display_name=""):
        now = time.time()
        password_hash = self._password_hash(password)
        with self.connect() as db:
            row = db.execute("SELECT * FROM students WHERE email=?", (email,)).fetchone()
            if row and row["verified_at"]:
                return None
            if row:
                db.execute(
                    "UPDATE students SET display_name=?, password_hash=?, updated=?, disabled=0 WHERE id=?",
                    (display_name, password_hash, now, row["id"]),
                )
                return dict(db.execute("SELECT * FROM students WHERE id=?", (row["id"],)).fetchone())
            student_id = "ST-" + secrets.token_hex(8).upper()
            db.execute(
                "INSERT INTO students(id,email,display_name,password_hash,created,updated) VALUES(?,?,?,?,?,?)",
                (student_id, email, display_name, password_hash, now, now),
            )
            return dict(db.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone())

    def student(self, email):
        with self.connect() as db:
            row = db.execute("SELECT * FROM students WHERE email=?", (email,)).fetchone()
        return dict(row) if row else None

    def issue_code(self, email, purpose, secret, minutes):
        student = self.student(email)
        now = time.time()
        code = f"{secrets.randbelow(1_000_000):06d}"
        with self.connect() as db:
            db.execute("UPDATE verification_codes SET used_at=? WHERE email=? AND purpose=? AND used_at IS NULL", (now, email, purpose))
            db.execute(
                "INSERT INTO verification_codes(email,student_id,purpose,code_hash,expires,created) VALUES(?,?,?,?,?,?)",
                (email, student["id"] if student else None, purpose, self._code_hash(email, purpose, code, secret), now + minutes * 60, now),
            )
        return code

    def verify_code(self, email, purpose, code, secret, max_attempts):
        now = time.time()
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM verification_codes WHERE email=? AND purpose=? AND used_at IS NULL ORDER BY id DESC LIMIT 1",
                (email, purpose),
            ).fetchone()
            if not row or row["expires"] < now:
                return "expired", None
            if row["attempts"] >= max_attempts:
                return "locked", None
            expected = self._code_hash(email, purpose, code, secret)
            if not hmac.compare_digest(expected, row["code_hash"]):
                db.execute("UPDATE verification_codes SET attempts=attempts+1 WHERE id=?", (row["id"],))
                return "invalid", None
            db.execute("UPDATE verification_codes SET used_at=? WHERE id=?", (now, row["id"]))
            if purpose == "verify":
                db.execute("UPDATE students SET verified_at=?, updated=? WHERE email=?", (now, now, email))
            student = db.execute("SELECT * FROM students WHERE email=?", (email,)).fetchone()
        return "ok", (dict(student) if student else None)

    def student_login(self, email, password, hours):
        student = self.student(email)
        if not student or student["disabled"] or not student["verified_at"]:
            return None, "not_verified"
        if not self._password_matches(password, student["password_hash"]):
            return None, "invalid"
        token = secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute(
                "INSERT INTO student_sessions VALUES(?,?,?,?)",
                (digest(token), student["id"], time.time() + hours * 3600, time.time()),
            )
        return token, student

    def student_google_login(self, email, display_name, hours):
        now = time.time()
        with self.connect() as db:
            student = db.execute("SELECT * FROM students WHERE email=?", (email,)).fetchone()
            if student and student["disabled"]:
                return None, "disabled"
            if not student:
                student_id = "ST-" + secrets.token_hex(8).upper()
                # Google-authenticated accounts do not use this password hash;
                # password recovery can still set a local password later.
                db.execute(
                    "INSERT INTO students(id,email,display_name,password_hash,verified_at,created,updated) VALUES(?,?,?,?,?,?,?)",
                    (student_id, email, display_name, self._password_hash(secrets.token_urlsafe(32)), now, now, now),
                )
                student = db.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
            elif not student["verified_at"]:
                db.execute("UPDATE students SET verified_at=?, updated=? WHERE email=?", (now, now, email))
                student = db.execute("SELECT * FROM students WHERE email=?", (email,)).fetchone()
            token = secrets.token_urlsafe(32)
            db.execute(
                "INSERT INTO student_sessions VALUES(?,?,?,?)",
                (digest(token), student["id"], now + hours * 3600, now),
            )
        return token, dict(student)

    def student_user(self, token):
        with self.connect() as db:
            row = db.execute(
                "SELECT s.* FROM student_sessions ss JOIN students s ON s.id=ss.student_id WHERE ss.token=? AND ss.expires>? AND s.disabled=0",
                (digest(token or ""), time.time()),
            ).fetchone()
        return dict(row) if row else None

    def student_logout(self, token):
        with self.connect() as db:
            db.execute("DELETE FROM student_sessions WHERE token=?", (digest(token or ""),))

    def link_session(self, token, student_id):
        if not token:
            return
        with self.connect() as db:
            db.execute("UPDATE sessions SET student_id=? WHERE id=?", (student_id, digest(token)))

    def reset_password(self, email, password):
        with self.connect() as db:
            db.execute("UPDATE students SET password_hash=?, updated=? WHERE email=?", (self._password_hash(password), time.time(), email))

    def context(self, sid, value):
        with self.connect() as db:
            db.execute("UPDATE sessions SET context=? WHERE id=?", (value, sid))

    def messages(self, sid):
        with self.connect() as db:
            rows = db.execute(
                "SELECT role,payload,created FROM messages WHERE session=? ORDER BY id DESC LIMIT 40", (sid,)
            ).fetchall()
        return [{"role": r["role"], **json.loads(r["payload"]), "created": r["created"]} for r in reversed(rows)]

    def student_messages(self, student_id, limit=120):
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT m.role,m.payload,m.created
                FROM messages m JOIN sessions s ON s.id=m.session
                WHERE s.student_id=? ORDER BY m.id DESC LIMIT ?
                """,
                (student_id, limit),
            ).fetchall()
        return [{"role": r["role"], **json.loads(r["payload"]), "created": r["created"]} for r in reversed(rows)]

    def add_message(self, sid, role, payload):
        with self.connect() as db:
            db.execute(
                "INSERT INTO messages(session,role,payload,created) VALUES(?,?,?,?)",
                (sid, role, json.dumps(payload, ensure_ascii=False), time.time()),
            )

    def clear(self, sid):
        with self.connect() as db:
            db.execute("DELETE FROM messages WHERE session=?", (sid,))
            db.execute("UPDATE sessions SET context='' WHERE id=?", (sid,))

    def clear_student(self, student_id, sid):
        with self.connect() as db:
            db.execute(
                "DELETE FROM messages WHERE session IN (SELECT id FROM sessions WHERE student_id=?)",
                (student_id,),
            )
            db.execute("UPDATE sessions SET context='' WHERE student_id=?", (student_id,))
            # Preserve the active session for the caller even if the account
            # has no previous history.
            db.execute("UPDATE sessions SET context='' WHERE id=?", (sid,))

    def feedback(self, sid, request_id, rating, student_id=None):
        with self.connect() as db:
            if student_id:
                rows = db.execute(
                    "SELECT m.id,m.payload FROM messages m JOIN sessions s ON s.id=m.session "
                    "WHERE s.student_id=? AND m.role='assistant'",
                    (student_id,),
                ).fetchall()
            else:
                rows = db.execute("SELECT id,payload FROM messages WHERE session=? AND role='assistant'", (sid,)).fetchall()
            for row in rows:
                payload = json.loads(row["payload"])
                if payload.get("request_id") == request_id:
                    payload["feedback"] = rating
                    db.execute(
                        "UPDATE messages SET payload=? WHERE id=?", (json.dumps(payload, ensure_ascii=False), row["id"])
                    )
                    return True
        return False

    def tickets(self, sid=None, status=None):
        sql, args = "SELECT * FROM tickets WHERE 1=1", []
        if sid:
            sql += " AND session=?"
            args.append(sid)
        if status:
            sql += " AND status=?"
            args.append(status)
        with self.connect() as db:
            return [dict(r) for r in db.execute(sql + " ORDER BY created DESC", args).fetchall()]

    def ticket(self, ticket_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        return dict(row) if row else None

    def ticket_detail(self, ticket_id):
        with self.connect() as db:
            ticket = db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
            if not ticket:
                return None
            events = db.execute(
                "SELECT actor,action,created FROM ticket_events WHERE ticket_id=? ORDER BY id",
                (ticket_id,),
            ).fetchall()
        return {
            "ticket": dict(ticket),
            "events": [dict(event) for event in events],
        }

    def create_ticket(self, sid, key, summary, reason):
        now = time.time()
        with self.connect() as db:
            created = db.execute(
                "INSERT OR IGNORE INTO tickets(id,session,request_key,summary,reason,status,owner,reply,created,updated)"
                " VALUES(?,?,?,?,?,'waiting',NULL,'',?,?)",
                ("TS-" + secrets.token_hex(4).upper(), sid, key, summary, reason, now, now),
            ).rowcount
            row = db.execute("SELECT * FROM tickets WHERE session=? AND request_key=?", (sid, key)).fetchone()
            if created:
                ticket_event(db, row["id"], "created", actor="candidate")
        return dict(row)

    def claim(self, ticket, owner):
        with self.connect() as db:
            now = time.time()
            result = db.execute(
                "UPDATE tickets SET status='in_progress',owner=?,updated=?,claimed_at=? WHERE id=? AND status='waiting'",
                (owner, now, now, ticket),
            )
            if result.rowcount == 1:
                ticket_event(db, ticket, "claimed", actor=owner, to_owner=owner)
            return result.rowcount == 1

    def resolve(self, ticket, owner, reply):
        with self.connect() as db:
            now = time.time()
            result = db.execute(
                "UPDATE tickets SET status='resolved',reply=?,updated=?,resolved_at=?"
                " WHERE id=? AND status='in_progress' AND owner=?",
                (reply, now, now, ticket, owner),
            )
            if result.rowcount == 1:
                ticket_event(db, ticket, "resolved", actor=owner)
            return result.rowcount == 1

    def staff_login(self, username):
        token = secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute("INSERT INTO staff_sessions VALUES(?,?,?)", (digest(token), username, time.time() + 8 * 3600))
        return token

    def cancel(self, ticket, sid):
        with self.connect() as db:
            now = time.time()
            result = db.execute(
                "UPDATE tickets SET status='cancelled',updated=? WHERE id=? AND session=? AND status IN ('waiting','in_progress')",
                (now, ticket, sid),
            )
            if result.rowcount == 1:
                ticket_event(db, ticket, "cancelled", actor="candidate")
            return result.rowcount == 1

    def reject(self, ticket, owner, reason):
        with self.connect() as db:
            now = time.time()
            result = db.execute(
                "UPDATE tickets SET status='rejected',owner=?,reply=?,updated=?,resolved_at=?"
                " WHERE id=? AND (status='waiting' OR (status='in_progress' AND owner=?))",
                (owner, reason, now, now, ticket, owner),
            )
            if result.rowcount == 1:
                ticket_event(db, ticket, "rejected", actor=owner)
            return result.rowcount == 1

    def staff_user(self, token):
        with self.connect() as db:
            row = db.execute(
                "SELECT s.username FROM staff_sessions s JOIN users u ON u.username=s.username"
                " WHERE s.token=? AND s.expires>? AND u.role='officer' AND u.active=1",
                (digest(token or ""), time.time()),
            ).fetchone()
            return row[0] if row else None

    def logout(self, token):
        with self.connect() as db:
            db.execute("DELETE FROM staff_sessions WHERE token=?", (digest(token or ""),))

    def allowed(self, key, count=10, window=60):
        now = time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM limits WHERE key=?", (key,)).fetchone()
            if row and now - row["start"] < window:
                if row["count"] >= count:
                    return False
                db.execute("UPDATE limits SET count=count+1 WHERE key=?", (key,))
            else:
                db.execute("INSERT OR REPLACE INTO limits VALUES(?,?,1)", (key, now))
            return True

    def reserve_llm(self, maximum):
        day = time.strftime("%Y-%m-%d", time.gmtime())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO budgets VALUES(?,0)", (day,))
            return db.execute("UPDATE budgets SET calls=calls+1 WHERE day=? AND calls<?", (day, maximum)).rowcount == 1

    def record(self, kind, mode, latency, token_count=0):
        with self.connect() as db:
            db.execute(
                "INSERT INTO events(kind,mode,latency,tokens,created) VALUES(?,?,?,?,?)",
                (kind, mode, latency, token_count, time.time()),
            )

    def metrics(self):
        with self.connect() as db:
            counts = {r[0]: r[1] for r in db.execute("SELECT kind,COUNT(*) FROM events GROUP BY kind")}
            states = {r[0]: r[1] for r in db.execute("SELECT status,COUNT(*) FROM tickets GROUP BY status")}
            latencies = [r[0] for r in db.execute("SELECT latency FROM events ORDER BY latency")]
            total_tokens = db.execute("SELECT COALESCE(SUM(tokens),0) FROM events").fetchone()[0]
            calls = db.execute("SELECT COALESCE(SUM(calls),0) FROM budgets").fetchone()[0]
            oldest = db.execute(
                "SELECT id,created,updated FROM tickets WHERE status='waiting' ORDER BY created LIMIT 1"
            ).fetchone()
            local_now = time.localtime()
            today_start = time.mktime((local_now.tm_year, local_now.tm_mon, local_now.tm_mday, 0, 0, 0, -1, -1, -1))
            today_actions = {
                r[0]: r[1]
                for r in db.execute(
                    "SELECT action,COUNT(*) FROM ticket_events WHERE created>=? GROUP BY action",
                    (today_start,),
                )
            }
            event_rows = db.execute(
                "SELECT ticket_id,action,created FROM ticket_events ORDER BY created"
            ).fetchall()
        total = sum(counts.values())
        response_starts = {}
        response_times = []
        for row in event_rows:
            if row["action"] == "claimed":
                response_starts[row["ticket_id"]] = row["created"]
            elif row["action"] in {"resolved", "rejected", "cancelled"}:
                started = response_starts.get(row["ticket_id"])
                if started is not None and row["created"] >= started:
                    response_times.append(row["created"] - started)
                    response_starts.pop(row["ticket_id"], None)
        status_counts = {status: states.get(status, 0) for status in ["waiting", "in_progress", "resolved", "rejected", "cancelled"]}
        return {
            "total": total,
            "answered": counts.get("answered", 0),
            "outcomes": counts,
            "answer_rate": round(100 * counts.get("answered", 0) / total, 1) if total else None,
            "accuracy": None,
            "reduction": None,
            "tickets": status_counts,
            "tokens": total_tokens,
            "llm_calls": calls,
            "p95_ms": round(latencies[min(len(latencies) - 1, math_index(len(latencies)))], 1) if latencies else None,
            "ticket_metrics": {
                "resolved_today": today_actions.get("resolved", 0),
                "rejected_today": today_actions.get("rejected", 0),
                "cancelled_today": today_actions.get("cancelled", 0),
                "oldest_waiting": (
                    {
                        "id": oldest["id"],
                        "created": oldest["created"],
                        "age_seconds": max(0, time.time() - oldest["created"]),
                    }
                    if oldest
                    else None
                ),
                "average_handling_seconds": round(sum(response_times) / len(response_times), 1)
                if response_times
                else None,
            },
        }

    def purge(self, hours):
        with self.connect() as db:
            cutoff = time.time() - hours * 3600
            db.execute("DELETE FROM messages WHERE session IN (SELECT id FROM sessions WHERE updated<?)", (cutoff,))
            db.execute("DELETE FROM sessions WHERE updated<?", (cutoff,))
            db.execute("DELETE FROM staff_sessions WHERE expires<?", (time.time(),))
            db.execute("DELETE FROM admin_sessions WHERE expires<?", (time.time(),))
            db.execute(
                "DELETE FROM ticket_events WHERE ticket_id IN (SELECT id FROM tickets WHERE updated<?)",
                (time.time() - 30 * 86400,),
            )
            db.execute("DELETE FROM tickets WHERE updated<?", (time.time() - 30 * 86400,))
            db.execute("DELETE FROM ticket_events WHERE ticket_id NOT IN (SELECT id FROM tickets)")
            db.execute("DELETE FROM limits WHERE start<?", (time.time() - 86400,))
            db.execute("DELETE FROM verification_codes WHERE expires<? OR used_at<?", (time.time(), time.time() - 86400))
            db.execute("DELETE FROM student_sessions WHERE expires<?", (time.time(),))


def ticket_event(db, ticket, action, actor=None, from_owner=None, to_owner=None, note=None):
    """Append the small ticket history used by both staff and admin workflows."""
    user = "(SELECT id FROM users WHERE username=?)"
    db.execute(
        "INSERT INTO ticket_events(ticket_id,actor,actor_id,action,from_officer_id,to_officer_id,note,created)"
        f" VALUES(?,?,{user},?,{user},{user},?,?)",
        (ticket, actor or "candidate", actor, action, from_owner, to_owner, note, time.time()),
    )


def math_index(length):
    return max(0, int(length * 0.95 + 0.9999) - 1)
