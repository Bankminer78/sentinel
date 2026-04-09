"""Zettelkasten — linked note system."""
import time, json, re


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS zettels (
        id INTEGER PRIMARY KEY, title TEXT, content TEXT, tags TEXT,
        created_at REAL, updated_at REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS zettel_links (
        id INTEGER PRIMARY KEY, from_id INTEGER, to_id INTEGER, link_type TEXT
    )""")


def create_zettel(conn, title: str, content: str, tags: list = None) -> int:
    _ensure_tables(conn)
    now = time.time()
    cur = conn.execute(
        "INSERT INTO zettels (title, content, tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (title, content, json.dumps(tags or []), now, now))
    conn.commit()
    return cur.lastrowid


def get_zettel(conn, zettel_id: int) -> dict:
    _ensure_tables(conn)
    r = conn.execute("SELECT * FROM zettels WHERE id=?", (zettel_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    try:
        d["tags"] = json.loads(d.get("tags") or "[]")
    except Exception:
        d["tags"] = []
    return d


def update_zettel(conn, zettel_id: int, content: str = None, title: str = None):
    _ensure_tables(conn)
    updates = ["updated_at=?"]
    params = [time.time()]
    if content is not None:
        updates.append("content=?")
        params.append(content)
    if title is not None:
        updates.append("title=?")
        params.append(title)
    params.append(zettel_id)
    conn.execute(f"UPDATE zettels SET {', '.join(updates)} WHERE id=?", params)
    conn.commit()


def delete_zettel(conn, zettel_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM zettels WHERE id=?", (zettel_id,))
    conn.execute("DELETE FROM zettel_links WHERE from_id=? OR to_id=?",
                 (zettel_id, zettel_id))
    conn.commit()


def list_zettels(conn, limit: int = 100) -> list:
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT * FROM zettels ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["tags"] = json.loads(d.get("tags") or "[]")
        except Exception:
            d["tags"] = []
        result.append(d)
    return result


def link_zettels(conn, from_id: int, to_id: int, link_type: str = "related") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO zettel_links (from_id, to_id, link_type) VALUES (?, ?, ?)",
        (from_id, to_id, link_type))
    conn.commit()
    return cur.lastrowid


def get_links(conn, zettel_id: int) -> dict:
    _ensure_tables(conn)
    outgoing = [dict(r) for r in conn.execute(
        "SELECT * FROM zettel_links WHERE from_id=?", (zettel_id,)).fetchall()]
    incoming = [dict(r) for r in conn.execute(
        "SELECT * FROM zettel_links WHERE to_id=?", (zettel_id,)).fetchall()]
    return {"outgoing": outgoing, "incoming": incoming}


def unlink_zettels(conn, link_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM zettel_links WHERE id=?", (link_id,))
    conn.commit()


def search_zettels(conn, query: str) -> list:
    _ensure_tables(conn)
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM zettels WHERE title LIKE ? OR content LIKE ? ORDER BY updated_at DESC",
        (like, like)).fetchall()
    return [dict(r) for r in rows]


def zettels_by_tag(conn, tag: str) -> list:
    _ensure_tables(conn)
    like = f'%"{tag}"%'
    rows = conn.execute("SELECT * FROM zettels WHERE tags LIKE ?", (like,)).fetchall()
    return [dict(r) for r in rows]


def extract_mentions(content: str) -> list:
    """Find [[zettel title]] style mentions in content."""
    return re.findall(r"\[\[([^\]]+)\]\]", content)


def count_zettels(conn) -> int:
    _ensure_tables(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM zettels").fetchone()
    return r["c"] if r else 0


def orphan_zettels(conn) -> list:
    """Zettels with no links."""
    _ensure_tables(conn)
    rows = conn.execute("""
        SELECT * FROM zettels WHERE id NOT IN (
            SELECT from_id FROM zettel_links UNION SELECT to_id FROM zettel_links
        )
    """).fetchall()
    return [dict(r) for r in rows]
