"""Habit tracking — daily habits with streaks and completion rates."""
import time
import datetime as _dt
from . import db


def _ensure_table(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY, name TEXT, frequency TEXT DEFAULT 'daily',
            target INTEGER DEFAULT 1, created_at REAL
        );
        CREATE TABLE IF NOT EXISTS habit_log (
            id INTEGER PRIMARY KEY, habit_id INTEGER, date TEXT, count INTEGER DEFAULT 1,
            UNIQUE(habit_id, date)
        );
    """)


def _today():
    return _dt.date.today().strftime("%Y-%m-%d")


def add_habit(conn, name: str, frequency: str = "daily", target: int = 1) -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO habits (name, frequency, target, created_at) VALUES (?, ?, ?, ?)",
        (name, frequency, target, time.time()))
    conn.commit()
    return cur.lastrowid


def get_habits(conn) -> list:
    _ensure_table(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM habits ORDER BY id").fetchall()]


def log_habit(conn, habit_id: int, date_str: str = None) -> dict:
    _ensure_table(conn)
    d = date_str or _today()
    conn.execute(
        "INSERT INTO habit_log (habit_id, date, count) VALUES (?, ?, 1) "
        "ON CONFLICT(habit_id, date) DO UPDATE SET count = count + 1",
        (habit_id, d))
    conn.commit()
    r = conn.execute("SELECT * FROM habit_log WHERE habit_id=? AND date=?",
                     (habit_id, d)).fetchone()
    return dict(r)


def get_habit_stats(conn, habit_id: int) -> dict:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT date FROM habit_log WHERE habit_id=? ORDER BY date", (habit_id,)).fetchall()
    dates = [r["date"] for r in rows]
    total_days = len(dates)
    if not dates:
        return {"current_streak": 0, "longest_streak": 0, "total_days": 0, "completion_rate": 0.0}
    # streaks
    longest = cur = 1
    prev = _dt.date.fromisoformat(dates[0])
    for ds in dates[1:]:
        d = _dt.date.fromisoformat(ds)
        if (d - prev).days == 1:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 1
        prev = d
    today = _dt.date.today()
    last = _dt.date.fromisoformat(dates[-1])
    current_streak = cur if (today - last).days <= 1 else 0
    habit = conn.execute("SELECT created_at FROM habits WHERE id=?", (habit_id,)).fetchone()
    if habit:
        days_since = max(1, int((time.time() - habit["created_at"]) / 86400) + 1)
        rate = round(total_days / days_since * 100, 1)
    else:
        rate = 0.0
    return {"current_streak": current_streak, "longest_streak": longest,
            "total_days": total_days, "completion_rate": rate}


def delete_habit(conn, habit_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM habits WHERE id=?", (habit_id,))
    conn.execute("DELETE FROM habit_log WHERE habit_id=?", (habit_id,))
    conn.commit()


def get_todays_habits(conn) -> list:
    _ensure_table(conn)
    d = _today()
    rows = conn.execute(
        "SELECT h.*, COALESCE(l.count, 0) as count FROM habits h "
        "LEFT JOIN habit_log l ON l.habit_id=h.id AND l.date=? ORDER BY h.id", (d,)).fetchall()
    out = []
    for r in rows:
        h = dict(r)
        h["done"] = h["count"] >= h["target"]
        out.append(h)
    return out
