import hashlib
import secrets
import time

SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def hash_password(password):
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, **SCRYPT)
    return "scrypt$" + salt.hex() + "$" + key.hex()


def verify_password(password, stored):
    try:
        scheme, salt, key = (stored or "").split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **SCRYPT)
    except ValueError:
        return False
    return secrets.compare_digest(candidate.hex(), key)


def create_user(db, username, name, email, role, password):
    return db.execute(
        "INSERT INTO users(username,name,email,role,active,password_hash,created) VALUES(?,?,?,?,1,?,?)",
        (username, name, email, role, hash_password(password), time.time()),
    ).lastrowid


def seed_accounts(store, cfg):
    """Create the .env officer and admin once; never overwrite an existing account."""
    seeds = [
        (cfg.staff_username, "Cán bộ tuyển sinh", cfg.staff_username + "@staff.local", "officer", cfg.staff_password),
        (cfg.admin_username, "Quản trị viên", cfg.admin_username + "@admin.local", "admin", cfg.admin_password),
    ]
    with store.connect() as db:
        for username, name, email, role, password in seeds:
            if not db.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                create_user(db, username, name, email, role, password)


def authenticate(store, username, password, role):
    with store.connect() as db:
        row = db.execute(
            "SELECT username,password_hash FROM users WHERE username=? AND role=? AND active=1", (username, role)
        ).fetchone()
    if not row:
        hash_password(password)  # keep timing similar for unknown users
        return None
    return row["username"] if verify_password(password, row["password_hash"]) else None
