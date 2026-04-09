"""Weekly planner — plan the week ahead."""
import time
from datetime import datetime, timedelta


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS weekly_plans (
        id INTEGER PRIMARY KEY, week_start TEXT UNIQUE,
        theme TEXT, goals TEXT, big_three TEXT, notes TEXT, created_at REAL
    )""")


def _week_start() -> str:
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    return monday.strftime("%Y-%m-%d")


def create_plan(conn, theme: str = "", goals: str = "", big_three: str = "",
                notes: str = "", week_start: str = None) -> int:
    _ensure_table(conn)
    ws = week_start or _week_start()
    conn.execute(
        """INSERT OR REPLACE INTO weekly_plans (week_start, theme, goals, big_three, notes, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (ws, theme, goals, big_three, notes, time.time()))
    conn.commit()
    r = conn.execute("SELECT id FROM weekly_plans WHERE week_start=?", (ws,)).fetchone()
    return r["id"] if r else 0


def get_plan(conn, week_start: str = None) -> dict:
    _ensure_table(conn)
    ws = week_start or _week_start()
    r = conn.execute("SELECT * FROM weekly_plans WHERE week_start=?", (ws,)).fetchone()
    return dict(r) if r else None


def list_plans(conn, limit: int = 12) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM weekly_plans ORDER BY week_start DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def current_plan(conn) -> dict:
    return get_plan(conn)


def update_plan(conn, week_start: str, **fields):
    _ensure_table(conn)
    updates = []
    params = []
    for key in ("theme", "goals", "big_three", "notes"):
        if key in fields:
            updates.append(f"{key}=?")
            params.append(fields[key])
    if updates:
        params.append(week_start)
        conn.execute(
            f"UPDATE weekly_plans SET {','.join(updates)} WHERE week_start=?", params)
        conn.commit()


def delete_plan(conn, week_start: str):
    _ensure_table(conn)
    conn.execute("DELETE FROM weekly_plans WHERE week_start=?", (week_start,))
    conn.commit()


def search_plans(conn, query: str) -> list:
    _ensure_table(conn)
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM weekly_plans WHERE theme LIKE ? OR goals LIKE ? OR notes LIKE ?",
        (like, like, like)).fetchall()
    return [dict(r) for r in rows]


def total_plans(conn) -> int:
    _ensure_table(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM weekly_plans").fetchone()
    return r["c"] if r else 0


def has_plan_this_week(conn) -> bool:
    return current_plan(conn) is not None
