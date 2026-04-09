"""Book notes / knowledge vault — quotes and insights from books."""
import time


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS vault (
        id INTEGER PRIMARY KEY, source TEXT, content TEXT,
        type TEXT DEFAULT 'quote', tags TEXT, ts REAL
    )""")


def add_note(conn, source: str, content: str, note_type: str = "quote", tags: str = "") -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO vault (source, content, type, tags, ts) VALUES (?, ?, ?, ?, ?)",
        (source, content, note_type, tags, time.time()))
    conn.commit()
    return cur.lastrowid


def get_notes(conn, source: str = None, note_type: str = None, limit: int = 50) -> list:
    _ensure_table(conn)
    q = "SELECT * FROM vault WHERE 1=1"
    params = []
    if source:
        q += " AND source=?"
        params.append(source)
    if note_type:
        q += " AND type=?"
        params.append(note_type)
    q += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def get_sources(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT DISTINCT source, COUNT(*) as count FROM vault GROUP BY source"
    ).fetchall()
    return [dict(r) for r in rows]


def search_vault(conn, query: str) -> list:
    _ensure_table(conn)
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM vault WHERE content LIKE ? OR tags LIKE ? ORDER BY ts DESC",
        (like, like)).fetchall()
    return [dict(r) for r in rows]


def random_note(conn, source: str = None) -> dict:
    _ensure_table(conn)
    if source:
        r = conn.execute(
            "SELECT * FROM vault WHERE source=? ORDER BY RANDOM() LIMIT 1", (source,)).fetchone()
    else:
        r = conn.execute("SELECT * FROM vault ORDER BY RANDOM() LIMIT 1").fetchone()
    return dict(r) if r else None


def delete_note(conn, note_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM vault WHERE id=?", (note_id,))
    conn.commit()


def note_types(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT DISTINCT type, COUNT(*) as count FROM vault GROUP BY type").fetchall()
    return [dict(r) for r in rows]


def note_count(conn) -> int:
    _ensure_table(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM vault").fetchone()
    return r["c"] if r else 0
