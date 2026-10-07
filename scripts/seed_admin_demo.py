"""Seed demo officers, tickets in every status and their history for the admin screens.

Usage: python scripts/seed_admin_demo.py   (safe to run again; existing demo rows are kept)
"""

import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import get_settings  # noqa: E402
from src.services.accounts import create_user, seed_accounts  # noqa: E402
from src.services.admissions import Admissions  # noqa: E402
from src.services.knowledge import Knowledge  # noqa: E402
from src.services.store import Store  # noqa: E402

OFFICERS = [("cb_lan", "Nguyễn Thị Lan"), ("cb_minh", "Trần Văn Minh"), ("cb_hoa", "Lê Thu Hoa")]
DEMO_PASSWORD = "Demo@2026!"
H = 3600
# id, question, reason, status, officer, created (hours ago), claimed after (h), finished after claim (h)
TICKETS = [
    (
        "TS-DEMO01",
        "Em muốn hỏi học bổng cho sinh viên có hoàn cảnh khó khăn",
        "sensitive",
        "waiting",
        None,
        30,
        None,
        None,
    ),
    (
        "TS-DEMO02",
        "Điểm chuẩn ngành Khoa học máy tính năm nay dự kiến bao nhiêu?",
        "low_confidence",
        "waiting",
        None,
        27,
        None,
        None,
    ),
    (
        "TS-DEMO03",
        "Em cần gặp cán bộ để hỏi về hồ sơ xét tuyển tài năng",
        "user_request",
        "waiting",
        None,
        2,
        None,
        None,
    ),
    ("TS-DEMO04", "Thí sinh khuyết tật có được ưu tiên không?", "sensitive", "in_progress", "cb_lan", 6, 1, None),
    (
        "TS-DEMO05",
        "Chương trình tiên tiến có học hoàn toàn bằng tiếng Anh không?",
        "low_confidence",
        "in_progress",
        "cb_lan",
        5,
        0.5,
        None,
    ),
    (
        "TS-DEMO06",
        "Hạn nộp chứng chỉ IELTS để quy đổi điểm là khi nào?",
        "user_request",
        "in_progress",
        "cb_minh",
        4,
        2,
        None,
    ),
    ("TS-DEMO07", "Học phí ngành Kỹ thuật điện năm 2026?", "low_confidence", "resolved", "cb_minh", 48, 3, 2),
    ("TS-DEMO08", "Em có thể đổi nguyện vọng sau khi đăng ký không?", "user_request", "resolved", "cb_hoa", 40, 1, 1),
    (
        "TS-DEMO09",
        "Ký túc xá có ưu tiên tân sinh viên tỉnh xa không?",
        "low_confidence",
        "resolved",
        "cb_lan",
        20,
        0.5,
        3,
    ),
    ("TS-DEMO10", "Cho em số điện thoại riêng của thầy trưởng khoa", "sensitive", "rejected", "cb_hoa", 10, 1, 0.2),
]


def event(db, ticket, action, created, actor=None, from_owner=None, to_owner=None, note=None):
    user = "(SELECT id FROM users WHERE username=?)"
    db.execute(
        "INSERT INTO ticket_events(ticket_id,actor_id,action,from_officer_id,to_officer_id,note,created)"
        f" VALUES(?,{user},?,{user},{user},?,?)",
        (ticket, actor, action, from_owner, to_owner, note, created),
    )


def demo_answers(data_dir, store, cfg):
    """Ask the real extractive pipeline each question so answers and sources match the product."""
    fallback = {"response": "Nguồn tuyển sinh chưa sẵn sàng.", "kind": "error", "sources": [], "mode": "extractive"}
    knowledge = Knowledge(data_dir)
    try:
        knowledge.ingest()
    except Exception:
        return [fallback] * len(TICKETS)
    admissions = Admissions(knowledge, store, cfg.model_copy(update={"answer_mode": "extractive"}))

    async def ask_all():
        return [await admissions.answer(t[1]) for t in TICKETS]

    return asyncio.run(ask_all())


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = get_settings()
    if cfg.app_env == "production":
        raise SystemExit("Không seed dữ liệu demo trong môi trường production.")
    data_dir = Path(cfg.mvp_data_dir)
    data_dir = data_dir if data_dir.is_absolute() else ROOT / data_dir
    store = Store(data_dir / "mvp.db")
    seed_accounts(store, cfg)
    answers = demo_answers(data_dir, store, cfg)
    now = time.time()
    with store.connect() as db:
        for username, name in OFFICERS:
            if not db.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                create_user(db, username, name, username + "@demo.hust.test", "officer", DEMO_PASSWORD)
        added = 0
        for i, (tid, question, reason, status, owner, ago, claim_h, finish_h) in enumerate(TICKETS):
            session = f"demo-session-{i + 1}"
            existing = db.execute("SELECT created FROM tickets WHERE id=?", (tid,)).fetchone()
            created = existing[0] if existing else now - ago * H
            # Conversation is refreshed on every run so demo answers follow the current knowledge source.
            db.execute("DELETE FROM messages WHERE session=?", (session,))
            for offset, role, payload in [(120, "user", {"response": question}), (110, "assistant", answers[i])]:
                db.execute(
                    "INSERT INTO messages(session,role,payload,created) VALUES(?,?,?,?)",
                    (session, role, json.dumps(payload, ensure_ascii=False), created - offset),
                )
            if existing:
                continue
            claimed = created + claim_h * H if claim_h is not None else None
            finished = claimed + finish_h * H if finish_h is not None else None
            reply = {
                "resolved": "Cán bộ đã kiểm tra nguồn và phản hồi ứng viên.",
                "rejected": "Ngoài phạm vi tư vấn tuyển sinh.",
            }
            db.execute(
                "INSERT INTO tickets(id,session,request_key,summary,reason,status,owner,reply,created,updated,claimed_at,resolved_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    tid,
                    session,
                    "demo-" + tid,
                    question,
                    reason,
                    status,
                    owner,
                    reply.get(status, ""),
                    created,
                    finished or claimed or created,
                    claimed,
                    finished,
                ),
            )
            event(db, tid, "created", created)
            if claimed:
                first = "cb_lan" if tid == "TS-DEMO06" else owner
                event(db, tid, "claimed", claimed, actor=first, to_owner=first)
            if tid == "TS-DEMO06":  # One ticket that was moved between officers.
                event(
                    db,
                    tid,
                    "reassigned",
                    claimed + 0.5 * H,
                    actor=cfg.admin_username,
                    from_owner="cb_lan",
                    to_owner=owner,
                    note="Cân bằng tải giữa cán bộ",
                )
            if status in ("resolved", "rejected") and finished:
                event(db, tid, status, finished, actor=owner)
            added += 1
    print(f"Đã seed {len(OFFICERS)} cán bộ (mật khẩu {DEMO_PASSWORD}) và {added} ticket demo vào {store.path}.")
    print(f"Đăng nhập /admin bằng tài khoản '{cfg.admin_username}' (ADMIN_PASSWORD trong .env).")


if __name__ == "__main__":
    main()
