"""Undo stack — revert recent actions."""
import json, time
from . import db


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS undo_stack (
        id INTEGER PRIMARY KEY, action_type TEXT, payload TEXT,
        undo_data TEXT, ts REAL, undone INTEGER DEFAULT 0
    )""")


def record_action(conn, action_type: str, payload: dict, undo_data: dict):
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO undo_stack (action_type, payload, undo_data, ts, undone) "
        "VALUES (?, ?, ?, ?, 0)",
        (action_type, json.dumps(payload or {}), json.dumps(undo_data or {}), time.time()))
    conn.commit()
    return cur.lastrowid


def _row(r):
    d = dict(r)
    d["payload"] = json.loads(d["payload"]) if d["payload"] else {}
    d["undo_data"] = json.loads(d["undo_data"]) if d["undo_data"] else {}
    return d


def _apply_undo(conn, entry: dict):
    a = entry["action_type"]
    u = entry["undo_data"]
    if a == "delete_rule":
        conn.execute(
            "INSERT INTO rules (id, text, parsed, action, active, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (u.get("id"), u.get("text", ""), u.get("parsed", "{}"),
             u.get("action", "block"), u.get("active", 1), u.get("created_at", time.time())))
    elif a == "toggle_rule":
        conn.execute("UPDATE rules SET active=? WHERE id=?",
                     (u.get("active"), u.get("id")))
    elif a == "clear_seen":
        for d in u.get("domains", []):
            conn.execute(
                "INSERT OR REPLACE INTO seen_domains (domain, category, first_seen) VALUES (?,?,?)",
                (d.get("domain"), d.get("category"), d.get("first_seen", time.time())))
    conn.commit()


def undo(conn) -> dict:
    _ensure_table(conn)
    r = conn.execute(
        "SELECT * FROM undo_stack WHERE undone=0 ORDER BY id DESC LIMIT 1").fetchone()
    if not r:
        return None
    entry = _row(r)
    _apply_undo(conn, entry)
    conn.execute("UPDATE undo_stack SET undone=1 WHERE id=?", (entry["id"],))
    conn.commit()
    return entry


def redo(conn) -> dict:
    _ensure_table(conn)
    r = conn.execute(
        "SELECT * FROM undo_stack WHERE undone=1 ORDER BY id DESC LIMIT 1").fetchone()
    if not r:
        return None
    entry = _row(r)
    a = entry["action_type"]
    p = entry["payload"]
    if a == "delete_rule":
        conn.execute("DELETE FROM rules WHERE id=?", (p.get("id"),))
    elif a == "toggle_rule":
        conn.execute("UPDATE rules SET active = NOT active WHERE id=?", (p.get("id"),))
    elif a == "clear_seen":
        conn.execute("DELETE FROM seen_domains")
    conn.execute("UPDATE undo_stack SET undone=0 WHERE id=?", (entry["id"],))
    conn.commit()
    return entry


def get_undo_history(conn, limit: int = 10) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM undo_stack ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [_row(r) for r in rows]


def clear_undo_history(conn):
    _ensure_table(conn)
    conn.execute("DELETE FROM undo_stack")
    conn.commit()
