"""Eisenhower matrix — prioritize tasks by urgency and importance."""
import time


QUADRANTS = {
    "Q1": {"name": "Do First", "description": "Urgent and Important", "urgent": True, "important": True},
    "Q2": {"name": "Schedule", "description": "Not Urgent but Important", "urgent": False, "important": True},
    "Q3": {"name": "Delegate", "description": "Urgent but Not Important", "urgent": True, "important": False},
    "Q4": {"name": "Eliminate", "description": "Not Urgent, Not Important", "urgent": False, "important": False},
}


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS matrix_tasks (
        id INTEGER PRIMARY KEY, task TEXT, urgent INTEGER, important INTEGER,
        completed INTEGER DEFAULT 0, created_at REAL
    )""")


def add_task(conn, task: str, urgent: bool = False, important: bool = False) -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO matrix_tasks (task, urgent, important, created_at) VALUES (?, ?, ?, ?)",
        (task, 1 if urgent else 0, 1 if important else 0, time.time()))
    conn.commit()
    return cur.lastrowid


def get_quadrant(task_id: int, conn) -> str:
    _ensure_table(conn)
    r = conn.execute(
        "SELECT urgent, important FROM matrix_tasks WHERE id=?", (task_id,)).fetchone()
    if not r:
        return None
    if r["urgent"] and r["important"]:
        return "Q1"
    if not r["urgent"] and r["important"]:
        return "Q2"
    if r["urgent"] and not r["important"]:
        return "Q3"
    return "Q4"


def get_tasks_in_quadrant(conn, quadrant: str) -> list:
    _ensure_table(conn)
    q = QUADRANTS.get(quadrant)
    if not q:
        return []
    rows = conn.execute(
        "SELECT * FROM matrix_tasks WHERE urgent=? AND important=? AND completed=0",
        (1 if q["urgent"] else 0, 1 if q["important"] else 0)).fetchall()
    return [dict(r) for r in rows]


def get_all_tasks(conn, include_completed: bool = False) -> dict:
    _ensure_table(conn)
    result = {}
    for quad in QUADRANTS.keys():
        result[quad] = get_tasks_in_quadrant(conn, quad)
    return result


def complete_task(conn, task_id: int):
    _ensure_table(conn)
    conn.execute("UPDATE matrix_tasks SET completed=1 WHERE id=?", (task_id,))
    conn.commit()


def delete_task(conn, task_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM matrix_tasks WHERE id=?", (task_id,))
    conn.commit()


def move_task(conn, task_id: int, urgent: bool, important: bool):
    _ensure_table(conn)
    conn.execute(
        "UPDATE matrix_tasks SET urgent=?, important=? WHERE id=?",
        (1 if urgent else 0, 1 if important else 0, task_id))
    conn.commit()


def q1_count(conn) -> int:
    return len(get_tasks_in_quadrant(conn, "Q1"))


def overwhelmed(conn) -> bool:
    """Too many Q1 tasks means fire-fighting mode."""
    return q1_count(conn) >= 5


def advice(conn) -> str:
    counts = {q: len(get_tasks_in_quadrant(conn, q)) for q in QUADRANTS.keys()}
    if counts["Q1"] > 5:
        return "You're in firefighter mode. Focus on Q1 only today."
    if counts["Q4"] > 10:
        return "Too many Q4 tasks — eliminate these."
    if counts["Q2"] < counts["Q1"]:
        return "Spend more time in Q2 (important, not urgent) to reduce Q1 later."
    return "Good balance. Keep it up."


def list_quadrants() -> list:
    return [{"id": k, **v} for k, v in QUADRANTS.items()]
