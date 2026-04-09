"""Step counter — log daily steps and distance."""
import time
from datetime import datetime, timedelta


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS steps_log (
        date TEXT PRIMARY KEY, steps INTEGER, distance_km REAL,
        calories INTEGER, ts REAL
    )""")


DEFAULT_TARGET = 10000


def log_steps(conn, steps: int, date_str: str = None) -> int:
    _ensure_table(conn)
    d = date_str or datetime.now().strftime("%Y-%m-%d")
    # Approximate: 1000 steps ~= 0.762 km, 40 calories
    distance = round(steps * 0.000762, 2)
    calories = int(steps * 0.04)
    conn.execute(
        "INSERT OR REPLACE INTO steps_log (date, steps, distance_km, calories, ts) VALUES (?, ?, ?, ?, ?)",
        (d, steps, distance, calories, time.time()))
    conn.commit()
    return steps


def get_steps(conn, date_str: str = None) -> dict:
    _ensure_table(conn)
    d = date_str or datetime.now().strftime("%Y-%m-%d")
    r = conn.execute("SELECT * FROM steps_log WHERE date=?", (d,)).fetchone()
    return dict(r) if r else {"date": d, "steps": 0, "distance_km": 0, "calories": 0}


def total_steps(conn, days: int = 7) -> int:
    _ensure_table(conn)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    r = conn.execute(
        "SELECT COALESCE(SUM(steps), 0) as total FROM steps_log WHERE date >= ?",
        (cutoff,)).fetchone()
    return r["total"] or 0


def avg_daily_steps(conn, days: int = 7) -> int:
    return int(total_steps(conn, days) / days) if days > 0 else 0


def days_target_reached(conn, target: int = None, days: int = 30) -> int:
    _ensure_table(conn)
    t = target or DEFAULT_TARGET
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    r = conn.execute(
        "SELECT COUNT(*) as c FROM steps_log WHERE date >= ? AND steps >= ?",
        (cutoff, t)).fetchone()
    return r["c"]


def streak(conn, target: int = None) -> int:
    _ensure_table(conn)
    t = target or DEFAULT_TARGET
    current = datetime.now().date()
    days = 0
    while True:
        dstr = current.strftime("%Y-%m-%d")
        r = conn.execute(
            "SELECT steps FROM steps_log WHERE date=?", (dstr,)).fetchone()
        if r and r["steps"] >= t:
            days += 1
            current -= timedelta(days=1)
        else:
            if days == 0 and current == datetime.now().date():
                current -= timedelta(days=1)
                continue
            break
    return days


def progress_today(conn, target: int = None) -> dict:
    t = target or DEFAULT_TARGET
    today = get_steps(conn)
    return {
        "steps": today["steps"],
        "target": t,
        "percent": round(today["steps"] / t * 100, 1) if t > 0 else 0,
        "remaining": max(0, t - today["steps"]),
    }


def delete_log(conn, date_str: str):
    _ensure_table(conn)
    conn.execute("DELETE FROM steps_log WHERE date=?", (date_str,))
    conn.commit()


def weekly_total(conn) -> int:
    return total_steps(conn, days=7)


def monthly_total(conn) -> int:
    return total_steps(conn, days=30)
