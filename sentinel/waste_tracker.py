"""Waste tracker — track time wasted on distractions."""
import time
from datetime import datetime, timedelta


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS waste_log (
        id INTEGER PRIMARY KEY, activity TEXT, minutes INTEGER,
        category TEXT, regret_level INTEGER, date TEXT, ts REAL
    )""")


def log_waste(conn, activity: str, minutes: int, category: str = "other",
              regret_level: int = 5) -> int:
    _ensure_table(conn)
    date_str = datetime.now().strftime("%Y-%m-%d")
    cur = conn.execute(
        """INSERT INTO waste_log (activity, minutes, category, regret_level, date, ts)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (activity, minutes, category, regret_level, date_str, time.time()))
    conn.commit()
    return cur.lastrowid


def total_wasted_today(conn) -> int:
    _ensure_table(conn)
    today = datetime.now().strftime("%Y-%m-%d")
    r = conn.execute(
        "SELECT COALESCE(SUM(minutes), 0) as total FROM waste_log WHERE date=?",
        (today,)).fetchone()
    return r["total"] or 0


def total_wasted_week(conn) -> int:
    _ensure_table(conn)
    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    r = conn.execute(
        "SELECT COALESCE(SUM(minutes), 0) as total FROM waste_log WHERE date >= ?",
        (cutoff,)).fetchone()
    return r["total"] or 0


def top_wastes(conn, days: int = 30, limit: int = 10) -> list:
    _ensure_table(conn)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT activity, SUM(minutes) as total, COUNT(*) as occurrences
           FROM waste_log WHERE date >= ? GROUP BY activity ORDER BY total DESC LIMIT ?""",
        (cutoff, limit)).fetchall()
    return [dict(r) for r in rows]


def by_category(conn, days: int = 30) -> dict:
    _ensure_table(conn)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT category, SUM(minutes) as total FROM waste_log WHERE date >= ? GROUP BY category",
        (cutoff,)).fetchall()
    return {r["category"]: r["total"] for r in rows}


def avg_regret(conn, days: int = 30) -> float:
    _ensure_table(conn)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    r = conn.execute(
        "SELECT AVG(regret_level) as avg FROM waste_log WHERE date >= ?",
        (cutoff,)).fetchone()
    return round(r["avg"] or 0, 1)


def high_regret_items(conn, threshold: int = 8) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM waste_log WHERE regret_level >= ? ORDER BY regret_level DESC",
        (threshold,)).fetchall()
    return [dict(r) for r in rows]


def delete_entry(conn, entry_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM waste_log WHERE id=?", (entry_id,))
    conn.commit()


def get_log(conn, days: int = 7) -> list:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT * FROM waste_log WHERE ts > ? ORDER BY ts DESC", (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def waste_trend(conn, days: int = 14) -> str:
    _ensure_table(conn)
    from datetime import datetime
    log = get_log(conn, days)
    if len(log) < 4:
        return "stable"
    mid = len(log) // 2
    first_half = sum(r["minutes"] or 0 for r in log[mid:])
    second_half = sum(r["minutes"] or 0 for r in log[:mid])
    if second_half > first_half * 1.2:
        return "worsening"
    if second_half < first_half * 0.8:
        return "improving"
    return "stable"
