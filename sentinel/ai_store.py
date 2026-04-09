"""AI Store — generic K/V + document store the AI agent can use freely.

This is the universal data layer. Instead of dozens of specialized modules,
the AI agent gets one place to write whatever it needs (habits, journal,
goals, custom metrics — anything) under any namespace.

External agents (e.g. user's personal Claude) talk to this via /ai/* endpoints.
"""
import time, json
from datetime import datetime, timedelta


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS ai_kv (
        namespace TEXT, key TEXT, value TEXT, updated_at REAL,
        PRIMARY KEY (namespace, key)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS ai_docs (
        id INTEGER PRIMARY KEY, namespace TEXT, doc TEXT,
        created_at REAL, tags TEXT
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_docs_ns ON ai_docs(namespace)")


# --- Key/Value store ---

def kv_set(conn, namespace: str, key: str, value):
    """Set a value (any JSON-serializable type)."""
    _ensure_tables(conn)
    conn.execute(
        "INSERT OR REPLACE INTO ai_kv (namespace, key, value, updated_at) VALUES (?, ?, ?, ?)",
        (namespace, key, json.dumps(value), time.time()))
    conn.commit()


def kv_get(conn, namespace: str, key: str, default=None):
    _ensure_tables(conn)
    r = conn.execute(
        "SELECT value FROM ai_kv WHERE namespace=? AND key=?", (namespace, key)).fetchone()
    if r is None:
        return default
    try:
        return json.loads(r["value"])
    except Exception:
        return default


def kv_delete(conn, namespace: str, key: str):
    _ensure_tables(conn)
    conn.execute("DELETE FROM ai_kv WHERE namespace=? AND key=?", (namespace, key))
    conn.commit()


def kv_list(conn, namespace: str) -> dict:
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT key, value FROM ai_kv WHERE namespace=?", (namespace,)).fetchall()
    out = {}
    for r in rows:
        try:
            out[r["key"]] = json.loads(r["value"])
        except Exception:
            out[r["key"]] = r["value"]
    return out


def kv_namespaces(conn) -> list:
    _ensure_tables(conn)
    rows = conn.execute("SELECT DISTINCT namespace FROM ai_kv").fetchall()
    return [r["namespace"] for r in rows]


def kv_clear_namespace(conn, namespace: str):
    _ensure_tables(conn)
    conn.execute("DELETE FROM ai_kv WHERE namespace=?", (namespace,))
    conn.commit()


# --- Document store ---

def doc_add(conn, namespace: str, doc, tags: list = None) -> int:
    """Append a document to a namespace. Returns id."""
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO ai_docs (namespace, doc, created_at, tags) VALUES (?, ?, ?, ?)",
        (namespace, json.dumps(doc), time.time(), json.dumps(tags or [])))
    conn.commit()
    return cur.lastrowid


def doc_get(conn, doc_id: int) -> dict:
    _ensure_tables(conn)
    r = conn.execute("SELECT * FROM ai_docs WHERE id=?", (doc_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    try:
        d["doc"] = json.loads(d["doc"])
    except Exception:
        pass
    try:
        d["tags"] = json.loads(d.get("tags") or "[]")
    except Exception:
        d["tags"] = []
    return d


def doc_list(conn, namespace: str = None, limit: int = 100, since: float = None) -> list:
    _ensure_tables(conn)
    q = "SELECT * FROM ai_docs WHERE 1=1"
    params = []
    if namespace:
        q += " AND namespace=?"
        params.append(namespace)
    if since:
        q += " AND created_at >= ?"
        params.append(since)
    q += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["doc"] = json.loads(d["doc"])
        except Exception:
            pass
        try:
            d["tags"] = json.loads(d.get("tags") or "[]")
        except Exception:
            d["tags"] = []
        out.append(d)
    return out


def doc_delete(conn, doc_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM ai_docs WHERE id=?", (doc_id,))
    conn.commit()


def doc_search(conn, query: str, namespace: str = None, limit: int = 50) -> list:
    _ensure_tables(conn)
    like = f"%{query}%"
    if namespace:
        rows = conn.execute(
            "SELECT * FROM ai_docs WHERE namespace=? AND (doc LIKE ? OR tags LIKE ?) ORDER BY created_at DESC LIMIT ?",
            (namespace, like, like, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM ai_docs WHERE (doc LIKE ? OR tags LIKE ?) ORDER BY created_at DESC LIMIT ?",
            (like, like, limit)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["doc"] = json.loads(d["doc"])
        except Exception:
            pass
        out.append(d)
    return out


def doc_namespaces(conn) -> list:
    _ensure_tables(conn)
    rows = conn.execute("SELECT DISTINCT namespace FROM ai_docs").fetchall()
    return [r["namespace"] for r in rows]


def doc_count(conn, namespace: str = None) -> int:
    _ensure_tables(conn)
    if namespace:
        r = conn.execute(
            "SELECT COUNT(*) as c FROM ai_docs WHERE namespace=?", (namespace,)).fetchone()
    else:
        r = conn.execute("SELECT COUNT(*) as c FROM ai_docs").fetchone()
    return r["c"]


def doc_clear_namespace(conn, namespace: str):
    _ensure_tables(conn)
    conn.execute("DELETE FROM ai_docs WHERE namespace=?", (namespace,))
    conn.commit()


# --- Summary for the AI ---

def summary(conn) -> dict:
    """Tell the AI what it has stored."""
    _ensure_tables(conn)
    return {
        "kv_namespaces": kv_namespaces(conn),
        "doc_namespaces": doc_namespaces(conn),
        "kv_total": conn.execute("SELECT COUNT(*) as c FROM ai_kv").fetchone()["c"],
        "doc_total": doc_count(conn),
    }
