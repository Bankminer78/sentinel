"""Mood tracking with patterns."""
import time
from datetime import datetime, timedelta


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS mood_log (
        id INTEGER PRIMARY KEY, mood INTEGER, note TEXT, tags TEXT, ts REAL
    )""")


def log_mood(conn, mood: int, note: str = "", tags: list = None) -> int:
    """Log mood 1-10."""
    _ensure_table(conn)
    import json
    cur = conn.execute(
        "INSERT INTO mood_log (mood, note, tags, ts) VALUES (?, ?, ?, ?)",
        (int(mood), note, json.dumps(tags or []), time.time()))
    conn.commit()
    return cur.lastrowid


def get_moods(conn, days: int = 30) -> list:
    _ensure_table(conn)
    import json
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT * FROM mood_log WHERE ts > ? ORDER BY ts DESC", (cutoff,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["tags"] = json.loads(d.get("tags") or "[]")
        except Exception:
            d["tags"] = []
        result.append(d)
    return result


def average_mood(conn, days: int = 7) -> float:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute("SELECT AVG(mood) as avg FROM mood_log WHERE ts > ?", (cutoff,)).fetchone()
    return round(r["avg"] or 0, 1)


def mood_trend(conn, days: int = 14) -> str:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT mood FROM mood_log WHERE ts > ? ORDER BY ts ASC", (cutoff,)).fetchall()
    if len(rows) < 4:
        return "stable"
    moods = [r["mood"] for r in rows]
    mid = len(moods) // 2
    first_avg = sum(moods[:mid]) / mid
    second_avg = sum(moods[mid:]) / (len(moods) - mid)
    if second_avg > first_avg + 1:
        return "improving"
    if second_avg < first_avg - 1:
        return "declining"
    return "stable"


def mood_by_day_of_week(conn, days: int = 90) -> dict:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT mood, ts FROM mood_log WHERE ts > ?", (cutoff,)).fetchall()
    by_day = {}
    for r in rows:
        day = datetime.fromtimestamp(r["ts"]).strftime("%A")
        by_day.setdefault(day, []).append(r["mood"])
    return {day: round(sum(moods) / len(moods), 1) if moods else 0
            for day, moods in by_day.items()}


def mood_by_hour(conn, days: int = 30) -> dict:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT mood, ts FROM mood_log WHERE ts > ?", (cutoff,)).fetchall()
    by_hour = {}
    for r in rows:
        h = datetime.fromtimestamp(r["ts"]).hour
        by_hour.setdefault(h, []).append(r["mood"])
    return {h: round(sum(moods) / len(moods), 1) for h, moods in by_hour.items()}


def delete_mood(conn, mood_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM mood_log WHERE id=?", (mood_id,))
    conn.commit()
