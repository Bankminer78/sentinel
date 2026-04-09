"""OKRs — Objectives and Key Results tracking."""
import time
from datetime import datetime


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS objectives (
        id INTEGER PRIMARY KEY, text TEXT, quarter TEXT, created_at REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS key_results (
        id INTEGER PRIMARY KEY, objective_id INTEGER, text TEXT,
        target REAL, current REAL DEFAULT 0, unit TEXT
    )""")


def current_quarter() -> str:
    now = datetime.now()
    q = (now.month - 1) // 3 + 1
    return f"{now.year}-Q{q}"


def add_objective(conn, text: str, quarter: str = None) -> int:
    _ensure_tables(conn)
    q = quarter or current_quarter()
    cur = conn.execute(
        "INSERT INTO objectives (text, quarter, created_at) VALUES (?, ?, ?)",
        (text, q, time.time()))
    conn.commit()
    return cur.lastrowid


def get_objectives(conn, quarter: str = None) -> list:
    _ensure_tables(conn)
    if quarter:
        rows = conn.execute("SELECT * FROM objectives WHERE quarter=?", (quarter,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM objectives").fetchall()
    return [dict(r) for r in rows]


def delete_objective(conn, obj_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM objectives WHERE id=?", (obj_id,))
    conn.execute("DELETE FROM key_results WHERE objective_id=?", (obj_id,))
    conn.commit()


def add_key_result(conn, objective_id: int, text: str, target: float, unit: str = "") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO key_results (objective_id, text, target, current, unit) VALUES (?,?,?,0,?)",
        (objective_id, text, target, unit))
    conn.commit()
    return cur.lastrowid


def update_key_result(conn, kr_id: int, current: float):
    _ensure_tables(conn)
    conn.execute("UPDATE key_results SET current=? WHERE id=?", (current, kr_id))
    conn.commit()


def get_key_results(conn, objective_id: int) -> list:
    _ensure_tables(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM key_results WHERE objective_id=?", (objective_id,)).fetchall()]


def get_objective_progress(conn, obj_id: int) -> dict:
    _ensure_tables(conn)
    obj = conn.execute("SELECT * FROM objectives WHERE id=?", (obj_id,)).fetchone()
    if not obj:
        return None
    krs = get_key_results(conn, obj_id)
    if not krs:
        return {**dict(obj), "krs": [], "percent": 0}
    percents = [min(100, (kr["current"] / kr["target"] * 100)) if kr["target"] else 0 for kr in krs]
    avg = sum(percents) / len(percents)
    return {**dict(obj), "krs": krs, "percent": round(avg, 1)}


def quarterly_summary(conn, quarter: str = None) -> dict:
    _ensure_tables(conn)
    q = quarter or current_quarter()
    objs = get_objectives(conn, q)
    progresses = [get_objective_progress(conn, o["id"]) for o in objs]
    avg = sum(p["percent"] for p in progresses) / len(progresses) if progresses else 0
    return {"quarter": q, "objectives": progresses, "avg_percent": round(avg, 1)}
