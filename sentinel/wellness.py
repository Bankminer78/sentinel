"""Wellness reminders — hydration, eye strain, posture, energy."""
import time
from datetime import datetime


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS wellness_log (
        id INTEGER PRIMARY KEY, kind TEXT, value REAL, note TEXT, ts REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS wellness_reminders (
        id INTEGER PRIMARY KEY, kind TEXT, interval_minutes INTEGER,
        enabled INTEGER DEFAULT 1, last_triggered REAL DEFAULT 0
    )""")


def log_water(conn, ounces: float = 8):
    _ensure_tables(conn)
    conn.execute("INSERT INTO wellness_log (kind, value, ts) VALUES ('water', ?, ?)",
                 (ounces, time.time()))
    conn.commit()


def log_eye_break(conn):
    _ensure_tables(conn)
    conn.execute("INSERT INTO wellness_log (kind, ts) VALUES ('eye_break', ?)", (time.time(),))
    conn.commit()


def log_posture_check(conn, rating: int = 5):
    _ensure_tables(conn)
    conn.execute("INSERT INTO wellness_log (kind, value, ts) VALUES ('posture', ?, ?)",
                 (rating, time.time()))
    conn.commit()


def log_energy(conn, level: int):
    """Log energy level 1-10."""
    _ensure_tables(conn)
    conn.execute("INSERT INTO wellness_log (kind, value, ts) VALUES ('energy', ?, ?)",
                 (level, time.time()))
    conn.commit()


def daily_totals(conn, date_str: str = None) -> dict:
    _ensure_tables(conn)
    today = date_str or datetime.now().strftime("%Y-%m-%d")
    day_start = datetime.strptime(today, "%Y-%m-%d").timestamp()
    day_end = day_start + 86400
    water = conn.execute(
        "SELECT COALESCE(SUM(value), 0) as v FROM wellness_log WHERE kind='water' AND ts>=? AND ts<?",
        (day_start, day_end)).fetchone()["v"] or 0
    eye_breaks = conn.execute(
        "SELECT COUNT(*) as c FROM wellness_log WHERE kind='eye_break' AND ts>=? AND ts<?",
        (day_start, day_end)).fetchone()["c"]
    avg_posture = conn.execute(
        "SELECT AVG(value) as v FROM wellness_log WHERE kind='posture' AND ts>=? AND ts<?",
        (day_start, day_end)).fetchone()["v"]
    avg_energy = conn.execute(
        "SELECT AVG(value) as v FROM wellness_log WHERE kind='energy' AND ts>=? AND ts<?",
        (day_start, day_end)).fetchone()["v"]
    return {
        "water_oz": water,
        "eye_breaks": eye_breaks,
        "avg_posture": round(avg_posture, 1) if avg_posture else None,
        "avg_energy": round(avg_energy, 1) if avg_energy else None,
    }


def set_reminder(conn, kind: str, interval_minutes: int) -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO wellness_reminders (kind, interval_minutes) VALUES (?, ?)",
        (kind, interval_minutes))
    conn.commit()
    return cur.lastrowid


def get_reminders(conn) -> list:
    _ensure_tables(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM wellness_reminders WHERE enabled=1").fetchall()]


def delete_reminder(conn, reminder_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM wellness_reminders WHERE id=?", (reminder_id,))
    conn.commit()


def reminders_due(conn) -> list:
    _ensure_tables(conn)
    now = time.time()
    rows = conn.execute("""SELECT * FROM wellness_reminders WHERE enabled=1 AND
                           (last_triggered + interval_minutes*60) < ?""", (now,)).fetchall()
    return [dict(r) for r in rows]


def mark_reminder_triggered(conn, reminder_id: int):
    _ensure_tables(conn)
    conn.execute("UPDATE wellness_reminders SET last_triggered=? WHERE id=?",
                 (time.time(), reminder_id))
    conn.commit()
