"""Morning/evening rituals — structured routines with checklist items."""
import json
import time
import datetime as _dt


def _ensure_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS rituals (
            id INTEGER PRIMARY KEY, name TEXT, time_of_day TEXT,
            items TEXT, created_at REAL
        );
        CREATE TABLE IF NOT EXISTS ritual_log (
            ritual_id INTEGER, date TEXT, completed_items TEXT,
            PRIMARY KEY(ritual_id, date)
        );
    """)
    conn.commit()


def _today():
    return _dt.date.today().strftime("%Y-%m-%d")


def create_ritual(conn, name: str, time_of_day: str, items: list) -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO rituals (name, time_of_day, items, created_at) VALUES (?, ?, ?, ?)",
        (name, time_of_day, json.dumps(items), time.time()))
    conn.commit()
    return cur.lastrowid


def _row_to_ritual(r):
    d = dict(r)
    d["items"] = json.loads(d["items"]) if d["items"] else []
    return d


def get_rituals(conn) -> list:
    _ensure_tables(conn)
    return [_row_to_ritual(r) for r in conn.execute(
        "SELECT * FROM rituals ORDER BY id").fetchall()]


def _get_ritual(conn, ritual_id):
    r = conn.execute("SELECT * FROM rituals WHERE id=?", (ritual_id,)).fetchone()
    return _row_to_ritual(r) if r else None


def start_ritual(conn, ritual_id: int) -> dict:
    _ensure_tables(conn)
    r = _get_ritual(conn, ritual_id)
    if not r:
        return None
    conn.execute(
        "INSERT OR REPLACE INTO ritual_log (ritual_id, date, completed_items) VALUES (?, ?, ?)",
        (ritual_id, _today(), json.dumps([])))
    conn.commit()
    return {"ritual_id": ritual_id, "name": r["name"], "items": r["items"], "completed": []}


def complete_ritual_item(conn, ritual_id: int, item_index: int):
    _ensure_tables(conn)
    r = conn.execute(
        "SELECT completed_items FROM ritual_log WHERE ritual_id=? AND date=?",
        (ritual_id, _today())).fetchone()
    completed = json.loads(r["completed_items"]) if r else []
    if item_index not in completed:
        completed.append(item_index)
    conn.execute(
        "INSERT OR REPLACE INTO ritual_log (ritual_id, date, completed_items) VALUES (?, ?, ?)",
        (ritual_id, _today(), json.dumps(completed)))
    conn.commit()


def get_ritual_progress(conn, ritual_id: int) -> dict:
    _ensure_tables(conn)
    r = _get_ritual(conn, ritual_id)
    if not r:
        return None
    row = conn.execute(
        "SELECT completed_items FROM ritual_log WHERE ritual_id=? AND date=?",
        (ritual_id, _today())).fetchone()
    completed = json.loads(row["completed_items"]) if row else []
    total = len(r["items"])
    return {"ritual_id": ritual_id, "name": r["name"], "total": total,
            "completed": len(completed), "completed_indices": completed,
            "percent": round(100 * len(completed) / total, 1) if total else 0.0}


def ritual_history(conn, ritual_id: int, days: int = 30) -> list:
    _ensure_tables(conn)
    cutoff = (_dt.date.today() - _dt.timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM ritual_log WHERE ritual_id=? AND date>=? ORDER BY date DESC",
        (ritual_id, cutoff)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["completed_items"] = json.loads(d["completed_items"]) if d["completed_items"] else []
        out.append(d)
    return out


def delete_ritual(conn, ritual_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM rituals WHERE id=?", (ritual_id,))
    conn.execute("DELETE FROM ritual_log WHERE ritual_id=?", (ritual_id,))
    conn.commit()
