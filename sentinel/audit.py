"""Audit log — every action is logged with hash chain."""
import hashlib, json, time


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY, action TEXT, details TEXT,
        ts REAL, prev_hash TEXT, hash TEXT
    )""")


def _compute_hash(prev_hash: str, action: str, details_json: str, ts: float) -> str:
    payload = f"{prev_hash}|{action}|{details_json}|{ts}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def get_last_hash(conn) -> str:
    _ensure_table(conn)
    r = conn.execute("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    return r["hash"] if r else ""


def log_action(conn, action: str, details: dict) -> int:
    _ensure_table(conn)
    prev = get_last_hash(conn)
    details_json = json.dumps(details or {}, sort_keys=True)
    ts = time.time()
    h = _compute_hash(prev, action, details_json, ts)
    cur = conn.execute(
        "INSERT INTO audit_log (action,details,ts,prev_hash,hash) VALUES (?,?,?,?,?)",
        (action, details_json, ts, prev, h))
    conn.commit()
    return cur.lastrowid


def _row(r):
    d = dict(r)
    try:
        d["details"] = json.loads(d["details"]) if d["details"] else {}
    except Exception:
        d["details"] = {}
    return d


def get_audit_log(conn, limit: int = 100) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [_row(r) for r in rows]


def verify_chain(conn) -> bool:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT id,action,details,ts,prev_hash,hash FROM audit_log ORDER BY id ASC").fetchall()
    prev = ""
    for r in rows:
        expected = _compute_hash(prev, r["action"], r["details"] or "{}", r["ts"])
        if r["prev_hash"] != prev or r["hash"] != expected:
            return False
        prev = r["hash"]
    return True


def purge_old(conn, days: int = 90) -> int:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    cur = conn.execute("DELETE FROM audit_log WHERE ts < ?", (cutoff,))
    conn.commit()
    return cur.rowcount or 0


def search_audit(conn, query: str) -> list:
    _ensure_table(conn)
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM audit_log WHERE action LIKE ? OR details LIKE ? ORDER BY id DESC",
        (like, like)).fetchall()
    return [_row(r) for r in rows]
