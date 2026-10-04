import hashlib
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
                    id TEXT PRIMARY KEY, context TEXT NOT NULL DEFAULT '', updated REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY, session TEXT NOT NULL, role TEXT NOT NULL,
                    payload TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS tickets (
                    id TEXT PRIMARY KEY, session TEXT NOT NULL, request_key TEXT NOT NULL,
                    summary TEXT NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL,
                    owner TEXT, reply TEXT NOT NULL DEFAULT '', created REAL NOT NULL,
                    updated REAL NOT NULL, UNIQUE(session, request_key));
                CREATE TABLE IF NOT EXISTS staff_sessions (
                    token TEXT PRIMARY KEY, username TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, kind TEXT NOT NULL, mode TEXT NOT NULL,
                    latency REAL NOT NULL, tokens INTEGER NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS budgets (day TEXT PRIMARY KEY, calls INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS limits (
                    key TEXT PRIMARY KEY, start REAL NOT NULL, count INTEGER NOT NULL);
            """)

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

    def session(self, token, hours):
        with self.connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (digest(token),)).fetchone() if token else None
            if row and row["updated"] > time.time() - hours * 3600:
                db.execute("UPDATE sessions SET updated=? WHERE id=?", (time.time(), row["id"]))
                return token, dict(row)
            token = secrets.token_urlsafe(32)
            row = {"id": digest(token), "context": "", "updated": time.time()}
            db.execute("INSERT INTO sessions(id, updated) VALUES(?,?)", (row["id"], row["updated"]))
            return token, row

    def context(self, sid, value):
        with self.connect() as db:
            db.execute("UPDATE sessions SET context=? WHERE id=?", (value, sid))

    def messages(self, sid):
        with self.connect() as db:
            rows = db.execute(
                "SELECT role,payload,created FROM messages WHERE session=? ORDER BY id DESC LIMIT 40", (sid,)
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

    def feedback(self, sid, request_id, rating):
        with self.connect() as db:
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

    def create_ticket(self, sid, key, summary, reason):
        now = time.time()
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO tickets VALUES(?,?,?,?,?,'waiting',NULL,'',?,?)",
                ("TS-" + secrets.token_hex(4).upper(), sid, key, summary, reason, now, now),
            )
            row = db.execute("SELECT * FROM tickets WHERE session=? AND request_key=?", (sid, key)).fetchone()
        return dict(row)

    def claim(self, ticket, owner):
        with self.connect() as db:
            result = db.execute(
                "UPDATE tickets SET status='in_progress',owner=?,updated=? WHERE id=? AND status='waiting'",
                (owner, time.time(), ticket),
            )
            return result.rowcount == 1

    def resolve(self, ticket, owner, reply):
        with self.connect() as db:
            result = db.execute(
                "UPDATE tickets SET status='resolved',reply=?,updated=? WHERE id=? AND status='in_progress' AND owner=?",
                (reply, time.time(), ticket, owner),
            )
            return result.rowcount == 1

    def staff_login(self, username):
        token = secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute("INSERT INTO staff_sessions VALUES(?,?,?)", (digest(token), username, time.time() + 8 * 3600))
        return token

    def cancel(self, ticket, sid):
        with self.connect() as db:
            return (
                db.execute(
                    "UPDATE tickets SET status='cancelled',updated=? WHERE id=? AND session=? AND status IN ('waiting','in_progress')",
                    (time.time(), ticket, sid),
                ).rowcount
                == 1
            )

    def reject(self, ticket, owner, reason):
        with self.connect() as db:
            return (
                db.execute(
                    "UPDATE tickets SET status='rejected',owner=?,reply=?,updated=? WHERE id=? AND (status='waiting' OR (status='in_progress' AND owner=?))",
                    (owner, reason, time.time(), ticket, owner),
                ).rowcount
                == 1
            )

    def staff_user(self, token):
        with self.connect() as db:
            row = db.execute(
                "SELECT username FROM staff_sessions WHERE token=? AND expires>?", (digest(token or ""), time.time())
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
        total = sum(counts.values())
        return {
            "total": total,
            "answered": counts.get("answered", 0),
            "outcomes": counts,
            "answer_rate": round(100 * counts.get("answered", 0) / total, 1) if total else None,
            "accuracy": None,
            "reduction": None,
            "tickets": states,
            "tokens": total_tokens,
            "llm_calls": calls,
            "p95_ms": round(latencies[min(len(latencies) - 1, math_index(len(latencies)))], 1) if latencies else None,
        }

    def purge(self, hours):
        with self.connect() as db:
            cutoff = time.time() - hours * 3600
            db.execute("DELETE FROM messages WHERE session IN (SELECT id FROM sessions WHERE updated<?)", (cutoff,))
            db.execute("DELETE FROM sessions WHERE updated<?", (cutoff,))
            db.execute("DELETE FROM staff_sessions WHERE expires<?", (time.time(),))
            db.execute("DELETE FROM tickets WHERE updated<?", (time.time() - 30 * 86400,))
            db.execute("DELETE FROM limits WHERE start<?", (time.time() - 86400,))


def math_index(length):
    return max(0, int(length * 0.95 + 0.9999) - 1)
