"""Fitness tracker — workouts, reps, sets, PRs."""
import time
from datetime import datetime, timedelta


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS workouts (
        id INTEGER PRIMARY KEY, name TEXT, type TEXT, duration_min INTEGER,
        calories INTEGER, notes TEXT, ts REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS exercises (
        id INTEGER PRIMARY KEY, workout_id INTEGER, name TEXT,
        sets INTEGER, reps INTEGER, weight REAL, ts REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS prs (
        id INTEGER PRIMARY KEY, exercise TEXT, value REAL, unit TEXT, date TEXT
    )""")


def log_workout(conn, name: str, workout_type: str = "general",
                duration_min: int = 0, calories: int = 0, notes: str = "") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO workouts (name, type, duration_min, calories, notes, ts) VALUES (?, ?, ?, ?, ?, ?)",
        (name, workout_type, duration_min, calories, notes, time.time()))
    conn.commit()
    return cur.lastrowid


def log_exercise(conn, workout_id: int, name: str, sets: int, reps: int, weight: float = 0) -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO exercises (workout_id, name, sets, reps, weight, ts) VALUES (?, ?, ?, ?, ?, ?)",
        (workout_id, name, sets, reps, weight, time.time()))
    conn.commit()
    # Check for PR
    check_pr(conn, name, weight * reps)  # simple 1RM estimate
    return cur.lastrowid


def get_workouts(conn, days: int = 30) -> list:
    _ensure_tables(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT * FROM workouts WHERE ts > ? ORDER BY ts DESC", (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def get_exercises(conn, workout_id: int) -> list:
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT * FROM exercises WHERE workout_id=?", (workout_id,)).fetchall()
    return [dict(r) for r in rows]


def total_workouts(conn, days: int = 30) -> int:
    _ensure_tables(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute("SELECT COUNT(*) as c FROM workouts WHERE ts > ?", (cutoff,)).fetchone()
    return r["c"]


def total_calories(conn, days: int = 30) -> int:
    _ensure_tables(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute(
        "SELECT COALESCE(SUM(calories), 0) as total FROM workouts WHERE ts > ?",
        (cutoff,)).fetchone()
    return r["total"] or 0


def total_duration(conn, days: int = 30) -> int:
    _ensure_tables(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute(
        "SELECT COALESCE(SUM(duration_min), 0) as total FROM workouts WHERE ts > ?",
        (cutoff,)).fetchone()
    return r["total"] or 0


def check_pr(conn, exercise: str, value: float) -> bool:
    """Check if value is a new PR. Returns True if new record."""
    _ensure_tables(conn)
    r = conn.execute(
        "SELECT value FROM prs WHERE exercise=?", (exercise,)).fetchone()
    if r is None or value > r["value"]:
        date_str = datetime.now().strftime("%Y-%m-%d")
        conn.execute(
            "INSERT OR REPLACE INTO prs (exercise, value, unit, date) VALUES (?, ?, 'volume', ?)",
            (exercise, value, date_str))
        conn.commit()
        return True
    return False


def get_prs(conn) -> list:
    _ensure_tables(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM prs ORDER BY value DESC").fetchall()]


def workout_streak(conn) -> int:
    _ensure_tables(conn)
    current = datetime.now().date()
    days = 0
    while True:
        day_start = datetime.combine(current, datetime.min.time()).timestamp()
        day_end = day_start + 86400
        r = conn.execute(
            "SELECT COUNT(*) as c FROM workouts WHERE ts >= ? AND ts < ?",
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


def by_type(conn, days: int = 30) -> dict:
    _ensure_tables(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT type, COUNT(*) as count FROM workouts WHERE ts > ? GROUP BY type",
        (cutoff,)).fetchall()
    return {r["type"]: r["count"] for r in rows}
