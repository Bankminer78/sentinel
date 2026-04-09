"""Daily/weekly time limits per category."""
import time
import datetime as _dt
from . import db


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS limits (
        id INTEGER PRIMARY KEY, category TEXT, period TEXT,
        max_seconds INTEGER, created_at REAL
    )""")


def set_limit(conn, category: str, period: str, max_seconds: int) -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO limits (category, period, max_seconds, created_at) VALUES (?, ?, ?, ?)",
        (category, period, max_seconds, time.time()))
    conn.commit()
    return cur.lastrowid


def get_limits(conn) -> list:
    _ensure_table(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM limits ORDER BY id").fetchall()]


def delete_limit(conn, limit_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM limits WHERE id=?", (limit_id,))
    conn.commit()


def _period_start(period: str) -> float:
    now = _dt.datetime.now()
    if period == "weekly":
        start = now - _dt.timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.timestamp()


def _usage_for_category(conn, category: str, period: str) -> int:
    since = _period_start(period)
    r = conn.execute(
        "SELECT COALESCE(SUM(a.duration_s), 0) as used "
        "FROM activity_log a LEFT JOIN seen_domains s ON s.domain=a.domain "
        "WHERE a.ts >= ? AND s.category=?",
        (since, category)).fetchone()
    return int(r["used"] or 0)


def check_limit(conn, category: str) -> dict:
    _ensure_table(conn)
    r = conn.execute(
        "SELECT * FROM limits WHERE category=? ORDER BY id DESC LIMIT 1",
        (category,)).fetchone()
    if not r:
        return {"used": 0, "limit": 0, "remaining": 0, "exceeded": False}
    used = _usage_for_category(conn, category, r["period"])
    limit = r["max_seconds"]
    return {"used": used, "limit": limit,
            "remaining": max(0, limit - used), "exceeded": used >= limit}


def get_all_limit_status(conn) -> list:
    _ensure_table(conn)
    out = []
    for r in conn.execute("SELECT * FROM limits ORDER BY id").fetchall():
        used = _usage_for_category(conn, r["category"], r["period"])
        limit = r["max_seconds"]
        out.append({
            "id": r["id"], "category": r["category"], "period": r["period"],
            "used": used, "limit": limit,
            "remaining": max(0, limit - used), "exceeded": used >= limit,
        })
    return out
