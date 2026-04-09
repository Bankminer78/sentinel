"""Sleep tracker — log sleep times and quality."""
import time
from datetime import datetime, timedelta


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS sleep_log (
        id INTEGER PRIMARY KEY, date TEXT UNIQUE, bedtime REAL, wake_time REAL,
        duration_hours REAL, quality INTEGER, notes TEXT
    )""")


def log_sleep(conn, bedtime_ts: float, wake_ts: float, quality: int = 5, notes: str = "") -> int:
    _ensure_table(conn)
    duration = (wake_ts - bedtime_ts) / 3600
    date_str = datetime.fromtimestamp(wake_ts).strftime("%Y-%m-%d")
    cur = conn.execute(
        """INSERT OR REPLACE INTO sleep_log (date, bedtime, wake_time, duration_hours, quality, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (date_str, bedtime_ts, wake_ts, round(duration, 2), quality, notes))
    conn.commit()
    return cur.lastrowid


def get_sleep(conn, date_str: str = None) -> dict:
    _ensure_table(conn)
    d = date_str or datetime.now().strftime("%Y-%m-%d")
    r = conn.execute("SELECT * FROM sleep_log WHERE date=?", (d,)).fetchone()
    return dict(r) if r else None


def get_last_n_days(conn, n: int = 7) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM sleep_log ORDER BY date DESC LIMIT ?", (n,)).fetchall()
    return [dict(r) for r in rows]


def avg_sleep_duration(conn, days: int = 7) -> float:
    _ensure_table(conn)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    r = conn.execute(
        "SELECT AVG(duration_hours) as avg FROM sleep_log WHERE date >= ?", (cutoff,)).fetchone()
    return round(r["avg"] or 0, 1)


def avg_sleep_quality(conn, days: int = 7) -> float:
    _ensure_table(conn)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    r = conn.execute(
        "SELECT AVG(quality) as avg FROM sleep_log WHERE date >= ?", (cutoff,)).fetchone()
    return round(r["avg"] or 0, 1)


def sleep_debt(conn, target_hours: float = 8.0, days: int = 7) -> float:
    """Cumulative hours below target."""
    sessions = get_last_n_days(conn, days)
    debt = 0
    for s in sessions:
        deficit = target_hours - (s.get("duration_hours") or 0)
        if deficit > 0:
            debt += deficit
    return round(debt, 1)


def nights_with_target(conn, target_hours: float = 7.0, days: int = 30) -> int:
    _ensure_table(conn)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    r = conn.execute(
        "SELECT COUNT(*) as c FROM sleep_log WHERE date >= ? AND duration_hours >= ?",
        (cutoff, target_hours)).fetchone()
    return r["c"]


def bedtime_consistency(conn, days: int = 14) -> float:
    """Standard deviation of bedtime (hours). Lower is better."""
    _ensure_table(conn)
    sessions = get_last_n_days(conn, days)
    if len(sessions) < 2:
        return 0
    bedtimes = [datetime.fromtimestamp(s["bedtime"]).hour + datetime.fromtimestamp(s["bedtime"]).minute / 60
                for s in sessions if s.get("bedtime")]
    if len(bedtimes) < 2:
        return 0
    mean = sum(bedtimes) / len(bedtimes)
    variance = sum((b - mean) ** 2 for b in bedtimes) / len(bedtimes)
    return round(variance ** 0.5, 2)


def delete_sleep(conn, date_str: str):
    _ensure_table(conn)
    conn.execute("DELETE FROM sleep_log WHERE date=?", (date_str,))
    conn.commit()
