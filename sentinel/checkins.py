"""Periodic check-ins — pop up every N minutes asking about focus."""
import time


def _ensure_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS checkins (
            id INTEGER PRIMARY KEY, interval_minutes INTEGER,
            last_triggered REAL, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS checkin_responses (
            id INTEGER PRIMARY KEY, checkin_id INTEGER, mood INTEGER,
            note TEXT, created_at REAL
        );
    """)
    conn.commit()


def schedule_checkin(conn, interval_minutes: int) -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO checkins (interval_minutes, last_triggered, active) VALUES (?, ?, 1)",
        (interval_minutes, time.time()))
    conn.commit()
    return cur.lastrowid


def cancel_checkin(conn, checkin_id: int):
    _ensure_tables(conn)
    conn.execute("UPDATE checkins SET active=0 WHERE id=?", (checkin_id,))
    conn.commit()


def get_active_checkins(conn) -> list:
    _ensure_tables(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM checkins WHERE active=1 ORDER BY id").fetchall()]


def record_response(conn, checkin_id: int, mood: int, note: str = "") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO checkin_responses (checkin_id, mood, note, created_at) VALUES (?, ?, ?, ?)",
        (checkin_id, mood, note, time.time()))
    conn.execute("UPDATE checkins SET last_triggered=? WHERE id=?",
                 (time.time(), checkin_id))
    conn.commit()
    return cur.lastrowid


def get_checkin_history(conn, limit: int = 50) -> list:
    _ensure_tables(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM checkin_responses ORDER BY created_at DESC LIMIT ?",
        (limit,)).fetchall()]


def time_until_next_checkin(conn) -> int:
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT interval_minutes, last_triggered FROM checkins WHERE active=1").fetchall()
    if not rows:
        return -1
    now = time.time()
    soonest = None
    for r in rows:
        next_t = (r["last_triggered"] or now) + r["interval_minutes"] * 60
        remaining = int(next_t - now)
        if soonest is None or remaining < soonest:
            soonest = remaining
    return max(0, soonest) if soonest is not None else -1


def should_checkin_now(conn) -> bool:
    t = time_until_next_checkin(conn)
    return t == 0
