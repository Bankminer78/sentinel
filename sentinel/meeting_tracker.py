"""Meeting tracker — log meetings and their effectiveness."""
import time
from datetime import datetime, timedelta


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS meetings (
        id INTEGER PRIMARY KEY, title TEXT, attendees TEXT,
        duration_min INTEGER, effectiveness INTEGER,
        action_items TEXT, notes TEXT, ts REAL
    )""")


def log_meeting(conn, title: str, duration_min: int, attendees: str = "",
                effectiveness: int = 5, action_items: str = "", notes: str = "") -> int:
    _ensure_table(conn)
    cur = conn.execute(
        """INSERT INTO meetings (title, attendees, duration_min, effectiveness, action_items, notes, ts)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (title, attendees, duration_min, effectiveness, action_items, notes, time.time()))
    conn.commit()
    return cur.lastrowid


def get_meetings(conn, days: int = 30) -> list:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT * FROM meetings WHERE ts > ? ORDER BY ts DESC", (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def get_meeting(conn, meeting_id: int) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
    return dict(r) if r else None


def delete_meeting(conn, meeting_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM meetings WHERE id=?", (meeting_id,))
    conn.commit()


def total_meeting_hours(conn, days: int = 7) -> float:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute(
        "SELECT COALESCE(SUM(duration_min), 0) as total FROM meetings WHERE ts > ?",
        (cutoff,)).fetchone()
    return round((r["total"] or 0) / 60, 1)


def avg_effectiveness(conn, days: int = 30) -> float:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute(
        "SELECT AVG(effectiveness) as avg FROM meetings WHERE ts > ?",
        (cutoff,)).fetchone()
    return round(r["avg"] or 0, 1)


def ineffective_meetings(conn, threshold: int = 3, days: int = 30) -> list:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT * FROM meetings WHERE effectiveness <= ? AND ts > ?",
        (threshold, cutoff)).fetchall()
    return [dict(r) for r in rows]


def meetings_by_day(conn, days: int = 7) -> dict:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT ts, duration_min FROM meetings WHERE ts > ?", (cutoff,)).fetchall()
    by_day = {}
    for r in rows:
        day = datetime.fromtimestamp(r["ts"]).strftime("%Y-%m-%d")
        by_day[day] = by_day.get(day, 0) + (r["duration_min"] or 0)
    return by_day


def search_meetings(conn, query: str) -> list:
    _ensure_table(conn)
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM meetings WHERE title LIKE ? OR notes LIKE ? OR action_items LIKE ?",
        (like, like, like)).fetchall()
    return [dict(r) for r in rows]


def total_count(conn, days: int = 7) -> int:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute("SELECT COUNT(*) as c FROM meetings WHERE ts > ?", (cutoff,)).fetchone()
    return r["c"]


def open_action_items(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT id, title, action_items FROM meetings WHERE action_items != '' ORDER BY ts DESC LIMIT 20"
    ).fetchall()
    return [dict(r) for r in rows]
