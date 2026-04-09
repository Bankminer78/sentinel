"""Simple todo list — tasks with priorities and due dates."""
import time
from datetime import datetime


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS todos (
        id INTEGER PRIMARY KEY, text TEXT, priority INTEGER DEFAULT 0,
        due_date TEXT, completed INTEGER DEFAULT 0, completed_at REAL,
        tags TEXT, created_at REAL
    )""")


def add_todo(conn, text: str, priority: int = 0, due_date: str = None, tags: str = "") -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO todos (text, priority, due_date, tags, created_at) VALUES (?, ?, ?, ?, ?)",
        (text, priority, due_date, tags, time.time()))
    conn.commit()
    return cur.lastrowid


def get_todos(conn, completed: bool = False) -> list:
    _ensure_table(conn)
    q = "SELECT * FROM todos WHERE completed=?"
    rows = conn.execute(q, (1 if completed else 0,)).fetchall()
    return sorted([dict(r) for r in rows], key=lambda t: (-t.get("priority", 0), t.get("created_at", 0)))


def complete_todo(conn, todo_id: int):
    _ensure_table(conn)
    conn.execute(
        "UPDATE todos SET completed=1, completed_at=? WHERE id=?",
        (time.time(), todo_id))
    conn.commit()


def uncomplete_todo(conn, todo_id: int):
    _ensure_table(conn)
    conn.execute("UPDATE todos SET completed=0, completed_at=NULL WHERE id=?", (todo_id,))
    conn.commit()


def delete_todo(conn, todo_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM todos WHERE id=?", (todo_id,))
    conn.commit()


def get_todo(conn, todo_id: int) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM todos WHERE id=?", (todo_id,)).fetchone()
    return dict(r) if r else None


def overdue_todos(conn) -> list:
    _ensure_table(conn)
    today = datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM todos WHERE completed=0 AND due_date IS NOT NULL AND due_date < ?",
        (today,)).fetchall()
    return [dict(r) for r in rows]


def due_today(conn) -> list:
    _ensure_table(conn)
    today = datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM todos WHERE completed=0 AND due_date=?", (today,)).fetchall()
    return [dict(r) for r in rows]


def high_priority(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM todos WHERE completed=0 AND priority >= 2 ORDER BY priority DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def todos_by_tag(conn, tag: str) -> list:
    _ensure_table(conn)
    like = f"%{tag}%"
    rows = conn.execute(
        "SELECT * FROM todos WHERE tags LIKE ?", (like,)).fetchall()
    return [dict(r) for r in rows]


def todo_count(conn) -> dict:
    _ensure_table(conn)
    total = conn.execute("SELECT COUNT(*) as c FROM todos").fetchone()["c"]
    done = conn.execute("SELECT COUNT(*) as c FROM todos WHERE completed=1").fetchone()["c"]
    return {"total": total, "done": done, "remaining": total - done}
