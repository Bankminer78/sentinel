"""Share rules, goals, and templates with others."""
import json, hashlib, base64, time
from . import db, importer


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS shares (
        code TEXT PRIMARY KEY, content_type TEXT, content_json TEXT,
        created_at REAL, revoked INTEGER DEFAULT 0
    )""")


_PREFIX = {"rule": "R", "goal": "G", "habit": "H", "template": "T", "all": "A"}


def _make_code(content_type: str, payload: str) -> str:
    h = hashlib.sha256(f"{content_type}:{payload}:{time.time()}".encode()).digest()
    return f"{_PREFIX.get(content_type, 'X')}-{base64.urlsafe_b64encode(h)[:8].decode()}"


def _gather(conn, content_type: str, content_id=None) -> dict:
    if content_type == "rule":
        rows = db.get_rules(conn, active_only=False)
        if content_id is not None:
            rows = [r for r in rows if r["id"] == content_id]
        return {"rules": [{"text": r["text"], "parsed": r.get("parsed") or "{}"} for r in rows]}
    if content_type == "goal":
        q = "SELECT * FROM goals" + (" WHERE id=?" if content_id else "")
        args = (content_id,) if content_id else ()
        rows = conn.execute(q, args).fetchall()
        return {"goals": [{"name": g["name"], "target_type": g["target_type"],
                           "target_value": g["target_value"], "category": g["category"]} for g in rows]}
    if content_type == "habit":
        conn.execute("""CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY, name TEXT, created_at REAL)""")
        rows = conn.execute("SELECT * FROM habits").fetchall()
        return {"habits": [{"name": h["name"]} for h in rows]}
    if content_type == "all":
        return importer.export_all(conn)
    return {}


def create_share_code(conn, content_type: str, content_id: int = None) -> str:
    _ensure_table(conn)
    bundle = _gather(conn, content_type, content_id)
    payload = json.dumps(bundle, sort_keys=True)
    code = _make_code(content_type, payload)
    conn.execute(
        "INSERT INTO shares (code,content_type,content_json,created_at,revoked) VALUES (?,?,?,?,0)",
        (code, content_type, payload, time.time()))
    conn.commit()
    return code


def get_share_bundle(conn, share_code: str) -> dict:
    _ensure_table(conn)
    r = conn.execute(
        "SELECT * FROM shares WHERE code=? AND revoked=0", (share_code,)).fetchone()
    if not r:
        return None
    return {"code": r["code"], "content_type": r["content_type"],
            "content": json.loads(r["content_json"]), "created_at": r["created_at"]}


def apply_share_code(conn, share_code: str, bundle: dict) -> dict:
    content = bundle.get("content", {}) if bundle else {}
    ctype = bundle.get("content_type") if bundle else None
    added, skipped = 0, 0
    if ctype == "rule" or "rules" in content:
        for r in content.get("rules", []):
            if r.get("text"):
                db.add_rule(conn, r["text"], {})
                added += 1
            else:
                skipped += 1
    if ctype == "goal" or "goals" in content:
        for g in content.get("goals", []):
            if g.get("name"):
                conn.execute(
                    "INSERT INTO goals (name,target_type,target_value,category,created_at) VALUES (?,?,?,?,?)",
                    (g["name"], g.get("target_type", "count"),
                     int(g.get("target_value") or 0), g.get("category"), time.time()))
                added += 1
    if ctype == "all":
        counts = importer.import_all(conn, content)
        added += sum(counts.values())
    conn.commit()
    return {"added": added, "skipped": skipped}


def list_my_shares(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT code,content_type,created_at,revoked FROM shares ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def revoke_share(conn, share_code: str):
    _ensure_table(conn)
    conn.execute("UPDATE shares SET revoked=1 WHERE code=?", (share_code,))
    conn.commit()


def export_share_bundle(content: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(content).encode("utf-8")).decode("ascii")


def import_share_bundle(encoded: str) -> dict:
    try:
        return json.loads(base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8"))
    except Exception:
        return {}
