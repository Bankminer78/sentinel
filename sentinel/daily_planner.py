"""Daily planner — structure your day with time blocks and priorities."""
import time
from datetime import datetime, timedelta


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS daily_plans (
        id INTEGER PRIMARY KEY, date TEXT UNIQUE, goals TEXT,
        priorities TEXT, notes TEXT, created_at REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS time_blocks (
        id INTEGER PRIMARY KEY, plan_id INTEGER, start_time TEXT,
        end_time TEXT, activity TEXT, completed INTEGER DEFAULT 0
    )""")


def create_plan(conn, date_str: str = None, goals: str = "", priorities: str = "") -> int:
    _ensure_tables(conn)
    d = date_str or datetime.now().strftime("%Y-%m-%d")
    cur = conn.execute(
        "INSERT OR REPLACE INTO daily_plans (date, goals, priorities, created_at) VALUES (?, ?, ?, ?)",
        (d, goals, priorities, time.time()))
    conn.commit()
    r = conn.execute("SELECT id FROM daily_plans WHERE date=?", (d,)).fetchone()
    return r["id"] if r else 0


def get_plan(conn, date_str: str = None) -> dict:
    _ensure_tables(conn)
    d = date_str or datetime.now().strftime("%Y-%m-%d")
    r = conn.execute("SELECT * FROM daily_plans WHERE date=?", (d,)).fetchone()
    if not r:
        return None
    d_dict = dict(r)
    blocks = conn.execute(
        "SELECT * FROM time_blocks WHERE plan_id=? ORDER BY start_time", (r["id"],)).fetchall()
    d_dict["blocks"] = [dict(b) for b in blocks]
    return d_dict


def add_block(conn, plan_id: int, start_time: str, end_time: str, activity: str) -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO time_blocks (plan_id, start_time, end_time, activity) VALUES (?, ?, ?, ?)",
        (plan_id, start_time, end_time, activity))
    conn.commit()
    return cur.lastrowid


def complete_block(conn, block_id: int):
    _ensure_tables(conn)
    conn.execute("UPDATE time_blocks SET completed=1 WHERE id=?", (block_id,))
    conn.commit()


def delete_block(conn, block_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM time_blocks WHERE id=?", (block_id,))
    conn.commit()


def list_plans(conn, limit: int = 30) -> list:
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT * FROM daily_plans ORDER BY date DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def plan_completion(conn, date_str: str = None) -> float:
    plan = get_plan(conn, date_str)
    if not plan or not plan.get("blocks"):
        return 0
    blocks = plan["blocks"]
    done = sum(1 for b in blocks if b["completed"])
    return round(done / len(blocks) * 100, 1) if blocks else 0


def update_plan(conn, date_str: str, goals: str = None, priorities: str = None, notes: str = None):
    _ensure_tables(conn)
    updates = []
    params = []
    if goals is not None:
        updates.append("goals=?")
        params.append(goals)
    if priorities is not None:
        updates.append("priorities=?")
        params.append(priorities)
    if notes is not None:
        updates.append("notes=?")
        params.append(notes)
    if updates:
        params.append(date_str)
        conn.execute(f"UPDATE daily_plans SET {','.join(updates)} WHERE date=?", params)
        conn.commit()


def completion_trend(conn, days: int = 14) -> float:
    _ensure_tables(conn)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    plans = [dict(r) for r in conn.execute(
        "SELECT date FROM daily_plans WHERE date >= ?", (cutoff,)).fetchall()]
    if not plans:
        return 0
    total = sum(plan_completion(conn, p["date"]) for p in plans)
    return round(total / len(plans), 1)
