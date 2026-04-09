"""Idea capture — quick capture of ideas with tagging and review."""
import time, json
from datetime import datetime


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS ideas (
        id INTEGER PRIMARY KEY, text TEXT, tags TEXT, starred INTEGER DEFAULT 0,
        reviewed INTEGER DEFAULT 0, ts REAL
    )""")


def capture(conn, text: str, tags: list = None) -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO ideas (text, tags, ts) VALUES (?, ?, ?)",
        (text, json.dumps(tags or []), time.time()))
    conn.commit()
    return cur.lastrowid


def get_ideas(conn, limit: int = 50, unreviewed_only: bool = False) -> list:
    _ensure_table(conn)
    q = "SELECT * FROM ideas"
    if unreviewed_only:
        q += " WHERE reviewed=0"
    q += " ORDER BY ts DESC LIMIT ?"
    rows = conn.execute(q, (limit,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["tags"] = json.loads(d.get("tags") or "[]")
        except Exception:
            d["tags"] = []
        result.append(d)
    return result


def star_idea(conn, idea_id: int):
    _ensure_table(conn)
    conn.execute("UPDATE ideas SET starred=1 WHERE id=?", (idea_id,))
    conn.commit()


def unstar_idea(conn, idea_id: int):
    _ensure_table(conn)
    conn.execute("UPDATE ideas SET starred=0 WHERE id=?", (idea_id,))
    conn.commit()


def mark_reviewed(conn, idea_id: int):
    _ensure_table(conn)
    conn.execute("UPDATE ideas SET reviewed=1 WHERE id=?", (idea_id,))
    conn.commit()


def delete_idea(conn, idea_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM ideas WHERE id=?", (idea_id,))
    conn.commit()


def starred_ideas(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute("SELECT * FROM ideas WHERE starred=1 ORDER BY ts DESC").fetchall()
    return [{**dict(r), "tags": json.loads(r["tags"] or "[]")} for r in rows]


def search_ideas(conn, query: str) -> list:
    _ensure_table(conn)
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM ideas WHERE text LIKE ? OR tags LIKE ? ORDER BY ts DESC",
        (like, like)).fetchall()
    return [{**dict(r), "tags": json.loads(r["tags"] or "[]")} for r in rows]


def ideas_by_tag(conn, tag: str) -> list:
    _ensure_table(conn)
    like = f'%"{tag}"%'
    rows = conn.execute(
        "SELECT * FROM ideas WHERE tags LIKE ? ORDER BY ts DESC", (like,)).fetchall()
    return [{**dict(r), "tags": json.loads(r["tags"] or "[]")} for r in rows]


def count(conn) -> int:
    _ensure_table(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM ideas").fetchone()
    return r["c"] if r else 0


def count_unreviewed(conn) -> int:
    _ensure_table(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM ideas WHERE reviewed=0").fetchone()
    return r["c"] if r else 0
