"""Long-term journeys — multi-week projects with milestones."""
import time
import json
from . import db


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS journeys (
        id INTEGER PRIMARY KEY, name TEXT, description TEXT,
        milestones TEXT, completed_indices TEXT, created_at REAL,
        completed_at REAL
    )""")


def _row_to_dict(r):
    d = dict(r)
    d["milestones"] = json.loads(d["milestones"]) if d["milestones"] else []
    d["completed_indices"] = json.loads(d["completed_indices"]) if d["completed_indices"] else []
    return d


def create_journey(conn, name: str, description: str, milestones: list) -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO journeys (name, description, milestones, completed_indices, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, description, json.dumps(milestones), json.dumps([]), time.time()))
    conn.commit()
    return cur.lastrowid


def get_journeys(conn, active: bool = True) -> list:
    _ensure_table(conn)
    if active:
        rows = conn.execute(
            "SELECT * FROM journeys WHERE completed_at IS NULL ORDER BY id").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM journeys WHERE completed_at IS NOT NULL ORDER BY id").fetchall()
    return [_row_to_dict(r) for r in rows]


def complete_milestone(conn, journey_id: int, milestone_index: int):
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM journeys WHERE id=?", (journey_id,)).fetchone()
    if not r:
        return
    j = _row_to_dict(r)
    if milestone_index < 0 or milestone_index >= len(j["milestones"]):
        return
    done = set(j["completed_indices"])
    done.add(milestone_index)
    completed_at = time.time() if len(done) == len(j["milestones"]) else None
    conn.execute(
        "UPDATE journeys SET completed_indices=?, completed_at=? WHERE id=?",
        (json.dumps(sorted(done)), completed_at, journey_id))
    conn.commit()


def get_journey_progress(conn, journey_id: int) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM journeys WHERE id=?", (journey_id,)).fetchone()
    if not r:
        return None
    j = _row_to_dict(r)
    total = len(j["milestones"])
    done = len(j["completed_indices"])
    pct = round(done / total * 100, 1) if total else 0.0
    return {"id": j["id"], "name": j["name"], "total": total,
            "completed": done, "percent": pct,
            "is_complete": j["completed_at"] is not None}


def delete_journey(conn, journey_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM journeys WHERE id=?", (journey_id,))
    conn.commit()
