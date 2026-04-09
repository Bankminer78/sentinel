"""Cron-like scheduled tasks — run Sentinel actions periodically."""
import time
from datetime import datetime


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS cron_tasks (
        id INTEGER PRIMARY KEY, name TEXT, expression TEXT,
        action TEXT, last_run REAL DEFAULT 0, enabled INTEGER DEFAULT 1
    )""")


def add_task(conn, name: str, expression: str, action: str) -> int:
    """Add a scheduled task.
    expression: '@hourly', '@daily', '@weekly', 'every 15 minutes', etc.
    action: function name or URL path to call."""
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO cron_tasks (name, expression, action) VALUES (?, ?, ?)",
        (name, expression, action))
    conn.commit()
    return cur.lastrowid


def list_tasks(conn) -> list:
    _ensure_table(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM cron_tasks").fetchall()]


def delete_task(conn, task_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM cron_tasks WHERE id=?", (task_id,))
    conn.commit()


def enable_task(conn, task_id: int):
    _ensure_table(conn)
    conn.execute("UPDATE cron_tasks SET enabled=1 WHERE id=?", (task_id,))
    conn.commit()


def disable_task(conn, task_id: int):
    _ensure_table(conn)
    conn.execute("UPDATE cron_tasks SET enabled=0 WHERE id=?", (task_id,))
    conn.commit()


def _expression_interval_seconds(expr: str) -> int:
    """Convert simple expression to seconds."""
    expr = expr.strip().lower()
    if expr == "@hourly":
        return 3600
    if expr == "@daily":
        return 86400
    if expr == "@weekly":
        return 604800
    if expr == "@monthly":
        return 2592000
    # "every N minutes"
    if "minute" in expr:
        parts = expr.split()
        for p in parts:
            if p.isdigit():
                return int(p) * 60
    # "every N hours"
    if "hour" in expr:
        parts = expr.split()
        for p in parts:
            if p.isdigit():
                return int(p) * 3600
    return 3600  # default hourly


def due_tasks(conn) -> list:
    """Get tasks that should run now."""
    _ensure_table(conn)
    now = time.time()
    rows = conn.execute("SELECT * FROM cron_tasks WHERE enabled=1").fetchall()
    due = []
    for r in rows:
        d = dict(r)
        interval = _expression_interval_seconds(d["expression"])
        if (d["last_run"] + interval) <= now:
            due.append(d)
    return due


def mark_task_run(conn, task_id: int):
    _ensure_table(conn)
    conn.execute("UPDATE cron_tasks SET last_run=? WHERE id=?", (time.time(), task_id))
    conn.commit()


def task_next_run(conn, task_id: int) -> float:
    """When will the task run next?"""
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM cron_tasks WHERE id=?", (task_id,)).fetchone()
    if not r:
        return 0
    interval = _expression_interval_seconds(r["expression"])
    return (r["last_run"] or 0) + interval
