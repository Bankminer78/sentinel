"""Eye strain prevention — 20-20-20 rule helper."""
import time


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS eye_breaks (
        id INTEGER PRIMARY KEY, ts REAL, duration_s INTEGER, type TEXT
    )""")


def log_break(conn, duration_s: int = 20, break_type: str = "20-20-20") -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO eye_breaks (ts, duration_s, type) VALUES (?, ?, ?)",
        (time.time(), duration_s, break_type))
    conn.commit()
    return cur.lastrowid


def time_since_last_break(conn) -> float:
    _ensure_table(conn)
    r = conn.execute("SELECT MAX(ts) as last FROM eye_breaks").fetchone()
    if not r or not r["last"]:
        return float('inf')
    return time.time() - r["last"]


def is_break_due(conn, interval_minutes: int = 20) -> bool:
    """Is it time for a 20-20-20 break?"""
    since = time_since_last_break(conn)
    return since >= interval_minutes * 60


def get_breaks_today(conn) -> int:
    _ensure_table(conn)
    from datetime import datetime
    today_start = datetime.combine(datetime.now().date(), datetime.min.time()).timestamp()
    r = conn.execute(
        "SELECT COUNT(*) as c FROM eye_breaks WHERE ts >= ?", (today_start,)).fetchone()
    return r["c"]


def get_breaks_log(conn, days: int = 7) -> list:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT * FROM eye_breaks WHERE ts > ? ORDER BY ts DESC", (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def breaks_per_day_avg(conn, days: int = 7) -> float:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute(
        "SELECT COUNT(*) as c FROM eye_breaks WHERE ts > ?", (cutoff,)).fetchone()
    return round(r["c"] / days, 1)


def get_break_tip() -> str:
    tips = [
        "Look at something 20 feet away for 20 seconds.",
        "Blink deliberately 10 times.",
        "Close your eyes for 20 seconds.",
        "Look out a window at the horizon.",
        "Gentle eye massage for 15 seconds.",
        "Trace a figure-8 with your eyes.",
        "Focus on your hand, then far away, repeat 5 times.",
    ]
    import random
    return random.choice(tips)


def should_notify(conn, interval_minutes: int = 20) -> bool:
    return is_break_due(conn, interval_minutes)
