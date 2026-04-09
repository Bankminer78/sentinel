"""Macros — run sequences of Sentinel actions."""
import time, json


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS macros (
        id INTEGER PRIMARY KEY, name TEXT UNIQUE, description TEXT,
        actions TEXT, created_at REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS macro_runs (
        id INTEGER PRIMARY KEY, macro_id INTEGER, ts REAL, status TEXT
    )""")


def create_macro(conn, name: str, actions: list, description: str = "") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT OR IGNORE INTO macros (name, description, actions, created_at) VALUES (?, ?, ?, ?)",
        (name, description, json.dumps(actions), time.time()))
    conn.commit()
    return cur.lastrowid or 0


def get_macros(conn) -> list:
    _ensure_tables(conn)
    rows = conn.execute("SELECT * FROM macros").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["actions"] = json.loads(d.get("actions") or "[]")
        except Exception:
            d["actions"] = []
        result.append(d)
    return result


def get_macro(conn, macro_id: int) -> dict:
    _ensure_tables(conn)
    r = conn.execute("SELECT * FROM macros WHERE id=?", (macro_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    try:
        d["actions"] = json.loads(d.get("actions") or "[]")
    except Exception:
        d["actions"] = []
    return d


def get_macro_by_name(conn, name: str) -> dict:
    _ensure_tables(conn)
    r = conn.execute("SELECT * FROM macros WHERE name=?", (name,)).fetchone()
    if not r:
        return None
    d = dict(r)
    try:
        d["actions"] = json.loads(d.get("actions") or "[]")
    except Exception:
        d["actions"] = []
    return d


def delete_macro(conn, macro_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM macros WHERE id=?", (macro_id,))
    conn.commit()


def log_run(conn, macro_id: int, status: str = "success") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO macro_runs (macro_id, ts, status) VALUES (?, ?, ?)",
        (macro_id, time.time(), status))
    conn.commit()
    return cur.lastrowid


def get_run_history(conn, macro_id: int = None, limit: int = 50) -> list:
    _ensure_tables(conn)
    if macro_id:
        rows = conn.execute(
            "SELECT * FROM macro_runs WHERE macro_id=? ORDER BY ts DESC LIMIT ?",
            (macro_id, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM macro_runs ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def total_macros(conn) -> int:
    _ensure_tables(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM macros").fetchone()
    return r["c"]


def update_macro(conn, macro_id: int, actions: list = None, description: str = None):
    _ensure_tables(conn)
    updates = []
    params = []
    if actions is not None:
        updates.append("actions=?")
        params.append(json.dumps(actions))
    if description is not None:
        updates.append("description=?")
        params.append(description)
    if updates:
        params.append(macro_id)
        conn.execute(f"UPDATE macros SET {','.join(updates)} WHERE id=?", params)
        conn.commit()
