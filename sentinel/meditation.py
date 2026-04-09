"""Guided meditation sessions."""
import time, json


SESSIONS = {
    "breathing_5min": {"name": "5-min Breathing", "duration_s": 300, "type": "breathing"},
    "breathing_10min": {"name": "10-min Breathing", "duration_s": 600, "type": "breathing"},
    "body_scan": {"name": "10-min Body Scan", "duration_s": 600, "type": "body_scan"},
    "loving_kindness": {"name": "15-min Loving Kindness", "duration_s": 900, "type": "loving_kindness"},
    "mindfulness": {"name": "20-min Mindfulness", "duration_s": 1200, "type": "mindfulness"},
    "box_breathing": {"name": "4x4 Box Breathing", "duration_s": 240, "type": "breathing"},
    "4_7_8": {"name": "4-7-8 Breathing", "duration_s": 180, "type": "breathing"},
}


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS meditation_log (
        id INTEGER PRIMARY KEY, session_id TEXT, start_ts REAL, end_ts REAL, completed INTEGER
    )""")


def list_sessions() -> list:
    return [{"id": k, **v} for k, v in SESSIONS.items()]


def start_session(conn, session_id: str) -> int:
    _ensure_table(conn)
    if session_id not in SESSIONS:
        return 0
    cur = conn.execute(
        "INSERT INTO meditation_log (session_id, start_ts, completed) VALUES (?, ?, 0)",
        (session_id, time.time()))
    conn.commit()
    return cur.lastrowid


def complete_session(conn, log_id: int):
    _ensure_table(conn)
    conn.execute(
        "UPDATE meditation_log SET end_ts=?, completed=1 WHERE id=?",
        (time.time(), log_id))
    conn.commit()


def get_sessions_log(conn, days: int = 30) -> list:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT * FROM meditation_log WHERE start_ts > ? ORDER BY start_ts DESC",
        (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def total_minutes(conn, days: int = 30) -> float:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute("""SELECT COALESCE(SUM(end_ts - start_ts), 0) as total
                        FROM meditation_log WHERE completed=1 AND start_ts > ?""",
                     (cutoff,)).fetchone()
    return round((r["total"] or 0) / 60, 1)


def streak(conn) -> int:
    """Consecutive days with a completed meditation session."""
    _ensure_table(conn)
    from datetime import datetime, timedelta
    current = datetime.now().date()
    days = 0
    while True:
        day_start = datetime.combine(current, datetime.min.time()).timestamp()
        day_end = day_start + 86400
        r = conn.execute("""SELECT COUNT(*) as c FROM meditation_log
                            WHERE completed=1 AND start_ts >= ? AND start_ts < ?""",
                         (day_start, day_end)).fetchone()
        if r["c"] > 0:
            days += 1
            current -= timedelta(days=1)
        else:
            if days == 0 and current == datetime.now().date():
                current -= timedelta(days=1)
                continue
            break
    return days
