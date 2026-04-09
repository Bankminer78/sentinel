"""Activity snapshots — periodic state captures for diff/restore."""
import time, json
from . import db as _db


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY, ts REAL, state TEXT, trigger TEXT
    )""")
    conn.commit()


def _capture_state(conn) -> dict:
    rules = [dict(r) for r in conn.execute("SELECT * FROM rules").fetchall()]
    goals = [dict(r) for r in conn.execute("SELECT * FROM goals").fetchall()]
    cfg = {r["key"]: r["value"] for r in conn.execute("SELECT key,value FROM config").fetchall()}
    from . import blocker
    blocked = blocker.get_blocked()
    return {"rules": rules, "goals": goals, "blocked": blocked, "config": cfg}


def take_snapshot(conn, trigger: str = "manual") -> int:
    _ensure_table(conn)
    state = _capture_state(conn)
    cur = conn.execute(
        "INSERT INTO snapshots (ts, state, trigger) VALUES (?, ?, ?)",
        (time.time(), json.dumps(state), trigger))
    conn.commit()
    return cur.lastrowid


def get_snapshot(conn, snapshot_id: int) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["state"] = json.loads(d["state"]) if d["state"] else {}
    return d


def list_snapshots(conn, limit: int = 50) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT id, ts, trigger FROM snapshots ORDER BY ts DESC LIMIT ?",
        (limit,)).fetchall()
    return [dict(r) for r in rows]


def _diff_list(a: list, b: list, key: str = "id") -> dict:
    ak = {x.get(key): x for x in a}
    bk = {x.get(key): x for x in b}
    added = [bk[k] for k in bk if k not in ak]
    removed = [ak[k] for k in ak if k not in bk]
    return {"added": added, "removed": removed}


def diff_snapshots(conn, id_a: int, id_b: int) -> dict:
    a = get_snapshot(conn, id_a)
    b = get_snapshot(conn, id_b)
    if not a or not b:
        return {"error": "not found"}
    sa, sb = a["state"], b["state"]
    return {
        "rules": _diff_list(sa.get("rules", []), sb.get("rules", [])),
        "goals": _diff_list(sa.get("goals", []), sb.get("goals", [])),
        "config_changed": [k for k in set(sa.get("config", {})) | set(sb.get("config", {}))
                           if sa.get("config", {}).get(k) != sb.get("config", {}).get(k)],
    }


def delete_snapshot(conn, snapshot_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM snapshots WHERE id=?", (snapshot_id,))
    conn.commit()


def periodic_snapshot(conn, interval_hours: int = 24) -> dict:
    _ensure_table(conn)
    r = conn.execute(
        "SELECT ts FROM snapshots WHERE trigger='periodic' ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    now = time.time()
    if r and (now - r["ts"]) < interval_hours * 3600:
        return {"taken": False, "id": None}
    sid = take_snapshot(conn, trigger="periodic")
    return {"taken": True, "id": sid}
