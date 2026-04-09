"""Lockdown mode — absolute blocking that can't be disabled."""
import hashlib, time


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS lockdown (
        id INTEGER PRIMARY KEY, start_ts REAL, end_ts REAL,
        password_hash TEXT, active INTEGER DEFAULT 1
    )""")


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _active_row(conn):
    _ensure_table(conn)
    r = conn.execute(
        "SELECT * FROM lockdown WHERE active=1 ORDER BY id DESC LIMIT 1").fetchone()
    return dict(r) if r else None


def enter_lockdown(conn, duration_minutes: int, password_hash: str = None) -> dict:
    _ensure_table(conn)
    now = time.time()
    end_ts = now + max(0, int(duration_minutes)) * 60
    cur = conn.execute(
        "INSERT INTO lockdown (start_ts,end_ts,password_hash,active) VALUES (?,?,?,1)",
        (now, end_ts, password_hash))
    conn.commit()
    return {"id": cur.lastrowid, "start_ts": now, "end_ts": end_ts,
            "duration_minutes": int(duration_minutes)}


def is_in_lockdown(conn) -> bool:
    row = _active_row(conn)
    if not row:
        return False
    if row["end_ts"] and time.time() >= row["end_ts"] and not row.get("password_hash"):
        # Auto-expire for passwordless lockdowns
        conn.execute("UPDATE lockdown SET active=0 WHERE id=?", (row["id"],))
        conn.commit()
        return False
    return True


def get_lockdown_end(conn) -> float | None:
    row = _active_row(conn)
    return row["end_ts"] if row else None


def try_exit_lockdown(conn, password: str = None) -> bool:
    row = _active_row(conn)
    if not row:
        return True
    now = time.time()
    # Password override — allowed any time
    if row.get("password_hash"):
        if password is None or _hash(password) != row["password_hash"]:
            return False
    else:
        # No password: must wait until end_ts
        if now < (row["end_ts"] or 0):
            return False
    conn.execute("UPDATE lockdown SET active=0 WHERE id=?", (row["id"],))
    conn.commit()
    return True


def extend_lockdown(conn, additional_minutes: int) -> None:
    row = _active_row(conn)
    if not row:
        return
    new_end = (row["end_ts"] or time.time()) + max(0, int(additional_minutes)) * 60
    conn.execute("UPDATE lockdown SET end_ts=? WHERE id=?", (new_end, row["id"]))
    conn.commit()


def emergency_contact(conn) -> str:
    """Who to call if locked out too long."""
    from sentinel import db
    return db.get_config(conn, "emergency_contact") or ""
