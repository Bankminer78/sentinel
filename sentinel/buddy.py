"""Accountability buddy system — pair up with someone for mutual accountability."""
import time


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS buddies (
        id INTEGER PRIMARY KEY, name TEXT, contact TEXT,
        relationship TEXT DEFAULT 'peer', check_in_frequency TEXT DEFAULT 'daily',
        added_at REAL, active INTEGER DEFAULT 1
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS buddy_messages (
        id INTEGER PRIMARY KEY, buddy_id INTEGER, direction TEXT,
        message TEXT, ts REAL
    )""")


def add_buddy(conn, name: str, contact: str, relationship: str = "peer",
              frequency: str = "daily") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO buddies (name, contact, relationship, check_in_frequency, added_at) VALUES (?, ?, ?, ?, ?)",
        (name, contact, relationship, frequency, time.time()))
    conn.commit()
    return cur.lastrowid


def get_buddies(conn, active_only: bool = True) -> list:
    _ensure_tables(conn)
    q = "SELECT * FROM buddies"
    if active_only:
        q += " WHERE active=1"
    return [dict(r) for r in conn.execute(q).fetchall()]


def remove_buddy(conn, buddy_id: int):
    _ensure_tables(conn)
    conn.execute("UPDATE buddies SET active=0 WHERE id=?", (buddy_id,))
    conn.commit()


def log_message(conn, buddy_id: int, direction: str, message: str) -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO buddy_messages (buddy_id, direction, message, ts) VALUES (?, ?, ?, ?)",
        (buddy_id, direction, message, time.time()))
    conn.commit()
    return cur.lastrowid


def get_messages(conn, buddy_id: int, limit: int = 50) -> list:
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT * FROM buddy_messages WHERE buddy_id=? ORDER BY ts DESC LIMIT ?",
        (buddy_id, limit)).fetchall()
    return [dict(r) for r in rows]


def last_check_in(conn, buddy_id: int) -> float:
    _ensure_tables(conn)
    r = conn.execute(
        "SELECT MAX(ts) as last FROM buddy_messages WHERE buddy_id=?", (buddy_id,)).fetchone()
    return r["last"] if r and r["last"] else 0


def buddies_needing_check_in(conn) -> list:
    """Buddies where it's been too long since the last check-in."""
    _ensure_tables(conn)
    now = time.time()
    out = []
    for b in get_buddies(conn):
        last = last_check_in(conn, b["id"])
        freq_s = 86400 if b["check_in_frequency"] == "daily" else 604800
        if now - last > freq_s:
            out.append({**b, "overdue_by_s": int(now - last - freq_s)})
    return out


def check_in(conn, buddy_id: int, message: str = "") -> int:
    """Log a check-in message to a buddy."""
    return log_message(conn, buddy_id, "out", message or "Check-in")


def receive_from_buddy(conn, buddy_id: int, message: str) -> int:
    return log_message(conn, buddy_id, "in", message)


def total_buddies(conn) -> int:
    _ensure_tables(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM buddies WHERE active=1").fetchone()
    return r["c"]
