"""Distraction log — manually log distractions as they happen."""
import time
from datetime import datetime


DISTRACTION_TYPES = [
    "internet", "phone", "social_media", "email", "colleague",
    "thought", "snack", "noise", "boredom", "anxiety", "other",
]


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS distraction_log (
        id INTEGER PRIMARY KEY, type TEXT, description TEXT,
        duration_s INTEGER, triggered_by TEXT, ts REAL
    )""")


def log_distraction(conn, type: str, description: str = "",
                    duration_s: int = 0, triggered_by: str = "") -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO distraction_log (type, description, duration_s, triggered_by, ts) VALUES (?, ?, ?, ?, ?)",
        (type, description, duration_s, triggered_by, time.time()))
    conn.commit()
    return cur.lastrowid


def get_distractions(conn, days: int = 7) -> list:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT * FROM distraction_log WHERE ts > ? ORDER BY ts DESC",
        (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def delete_distraction(conn, distraction_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM distraction_log WHERE id=?", (distraction_id,))
    conn.commit()


def count_by_type(conn, days: int = 7) -> dict:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT type, COUNT(*) as c FROM distraction_log WHERE ts > ? GROUP BY type",
        (cutoff,)).fetchall()
    return {r["type"]: r["c"] for r in rows}


def total_distracted_seconds(conn, days: int = 7) -> int:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute(
        "SELECT COALESCE(SUM(duration_s), 0) as total FROM distraction_log WHERE ts > ?",
        (cutoff,)).fetchone()
    return r["total"] or 0


def triggers_ranked(conn, days: int = 30) -> list:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT triggered_by, COUNT(*) as c FROM distraction_log WHERE ts > ? AND triggered_by != '' GROUP BY triggered_by ORDER BY c DESC",
        (cutoff,)).fetchall()
    return [{"trigger": r["triggered_by"], "count": r["c"]} for r in rows]


def distractions_by_hour(conn, days: int = 30) -> dict:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT ts FROM distraction_log WHERE ts > ?", (cutoff,)).fetchall()
    hours = {}
    for r in rows:
        h = datetime.fromtimestamp(r["ts"]).hour
        hours[h] = hours.get(h, 0) + 1
    return hours


def get_types() -> list:
    return list(DISTRACTION_TYPES)
