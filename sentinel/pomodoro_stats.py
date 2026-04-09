"""Detailed pomodoro statistics."""
import time
from datetime import datetime, timedelta


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS pomodoro_sessions (
        id INTEGER PRIMARY KEY, start_ts REAL, work_minutes INTEGER,
        break_minutes INTEGER, total_cycles INTEGER, current_cycle INTEGER,
        state TEXT, ended_at REAL
    )""")


def pomodoros_completed(conn, days: int = 7) -> int:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute(
        "SELECT COUNT(*) as c FROM pomodoro_sessions WHERE start_ts > ? AND state='done'",
        (cutoff,)).fetchone()
    return r["c"] if r else 0


def total_focus_minutes(conn, days: int = 7) -> int:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT work_minutes, total_cycles, current_cycle FROM pomodoro_sessions WHERE start_ts > ?",
        (cutoff,)).fetchall()
    total = 0
    for r in rows:
        total += (r["work_minutes"] or 0) * (r["current_cycle"] or 0)
    return total


def avg_session_length(conn, days: int = 30) -> float:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT ended_at - start_ts as duration FROM pomodoro_sessions WHERE start_ts > ? AND ended_at IS NOT NULL",
        (cutoff,)).fetchall()
    if not rows:
        return 0
    values = [r["duration"] for r in rows if r["duration"]]
    if not values:
        return 0
    return round(sum(values) / len(values) / 60, 1)


def pomodoros_per_day(conn, days: int = 30) -> dict:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT start_ts FROM pomodoro_sessions WHERE start_ts > ?", (cutoff,)).fetchall()
    by_day = {}
    for r in rows:
        day = datetime.fromtimestamp(r["start_ts"]).strftime("%Y-%m-%d")
        by_day[day] = by_day.get(day, 0) + 1
    return by_day


def best_day(conn) -> dict:
    per_day = pomodoros_per_day(conn, days=365)
    if not per_day:
        return None
    best_date = max(per_day, key=per_day.get)
    return {"date": best_date, "count": per_day[best_date]}


def pomodoro_streak(conn) -> int:
    _ensure_table(conn)
    current = datetime.now().date()
    days = 0
    while True:
        day_start = datetime.combine(current, datetime.min.time()).timestamp()
        day_end = day_start + 86400
        r = conn.execute(
            "SELECT COUNT(*) as c FROM pomodoro_sessions WHERE start_ts >= ? AND start_ts < ?",
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


def peak_hours(conn, days: int = 30) -> list:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT start_ts FROM pomodoro_sessions WHERE start_ts > ?", (cutoff,)).fetchall()
    from collections import Counter
    hours = Counter()
    for r in rows:
        h = datetime.fromtimestamp(r["start_ts"]).hour
        hours[h] += 1
    return [h for h, _ in hours.most_common(3)]


def completion_rate(conn, days: int = 30) -> float:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    total = conn.execute(
        "SELECT COUNT(*) as c FROM pomodoro_sessions WHERE start_ts > ?",
        (cutoff,)).fetchone()["c"]
    if total == 0:
        return 0
    completed = conn.execute(
        "SELECT COUNT(*) as c FROM pomodoro_sessions WHERE start_ts > ? AND state='done'",
        (cutoff,)).fetchone()["c"]
    return round(completed / total * 100, 1)


def weekly_focus_hours(conn) -> float:
    return round(total_focus_minutes(conn, days=7) / 60, 1)


def pomodoro_summary(conn) -> dict:
    return {
        "completed_this_week": pomodoros_completed(conn, days=7),
        "focus_hours_week": weekly_focus_hours(conn),
        "streak": pomodoro_streak(conn),
        "peak_hours": peak_hours(conn),
        "completion_rate": completion_rate(conn),
    }
