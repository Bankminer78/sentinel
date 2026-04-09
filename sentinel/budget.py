"""Time budgets — allocate time to categories."""
import time
from datetime import datetime, timedelta
from . import db


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS time_budgets (
        id INTEGER PRIMARY KEY, category TEXT, period TEXT,
        target_seconds INTEGER, created_at REAL
    )""")


def set_budget(conn, category: str, period: str, target_seconds: int) -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO time_budgets (category, period, target_seconds, created_at) VALUES (?,?,?,?)",
        (category, period, target_seconds, time.time()))
    conn.commit()
    return cur.lastrowid


def get_budgets(conn) -> list:
    _ensure_table(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM time_budgets ORDER BY id").fetchall()]


def get_budget(conn, budget_id: int) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM time_budgets WHERE id=?", (budget_id,)).fetchone()
    return dict(r) if r else None


def delete_budget(conn, budget_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM time_budgets WHERE id=?", (budget_id,))
    conn.commit()


def _get_period_start_ts(period: str) -> float:
    now = datetime.now()
    if period == "daily":
        return datetime.combine(now.date(), datetime.min.time()).timestamp()
    if period == "weekly":
        monday = now.date() - timedelta(days=now.weekday())
        return datetime.combine(monday, datetime.min.time()).timestamp()
    if period == "monthly":
        first = now.replace(day=1)
        return datetime.combine(first.date(), datetime.min.time()).timestamp()
    return 0


def check_budget_status(conn, budget_id: int) -> dict:
    _ensure_table(conn)
    b = get_budget(conn, budget_id)
    if not b:
        return None
    start = _get_period_start_ts(b["period"])
    # Sum activity_log.duration_s for domains matching this category
    used = 0
    activities = db.get_activities(conn, since=start, limit=10000)
    for a in activities:
        dom = a.get("domain")
        if dom:
            cat = db.get_seen(conn, dom)
            if cat == b["category"]:
                used += a.get("duration_s") or 0
    remaining = max(0, b["target_seconds"] - used)
    percent = min(100, (used / b["target_seconds"] * 100)) if b["target_seconds"] > 0 else 0
    return {
        **b,
        "used_seconds": used,
        "remaining_seconds": remaining,
        "exceeded": used > b["target_seconds"],
        "percent": round(percent, 1),
    }


def all_budgets_status(conn) -> list:
    return [check_budget_status(conn, b["id"]) for b in get_budgets(conn)]


def over_budget(conn) -> list:
    return [s for s in all_budgets_status(conn) if s and s["exceeded"]]
