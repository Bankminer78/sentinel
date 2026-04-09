"""Quick capture — fast inbox for any type of item (task, note, idea, quote)."""
import time


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS quick_capture (
        id INTEGER PRIMARY KEY, content TEXT, item_type TEXT,
        processed INTEGER DEFAULT 0, ts REAL
    )""")


TYPES = ["task", "note", "idea", "quote", "link", "reminder", "question", "other"]


def capture(conn, content: str, item_type: str = "note") -> int:
    _ensure_table(conn)
    if item_type not in TYPES:
        item_type = "other"
    cur = conn.execute(
        "INSERT INTO quick_capture (content, item_type, ts) VALUES (?, ?, ?)",
        (content, item_type, time.time()))
    conn.commit()
    return cur.lastrowid


def get_inbox(conn, unprocessed_only: bool = True) -> list:
    _ensure_table(conn)
    q = "SELECT * FROM quick_capture"
    if unprocessed_only:
        q += " WHERE processed=0"
    q += " ORDER BY ts DESC"
    rows = conn.execute(q).fetchall()
    return [dict(r) for r in rows]


def mark_processed(conn, item_id: int):
    _ensure_table(conn)
    conn.execute("UPDATE quick_capture SET processed=1 WHERE id=?", (item_id,))
    conn.commit()


def delete_item(conn, item_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM quick_capture WHERE id=?", (item_id,))
    conn.commit()


def process_all(conn):
    _ensure_table(conn)
    conn.execute("UPDATE quick_capture SET processed=1 WHERE processed=0")
    conn.commit()


def by_type(conn, item_type: str) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM quick_capture WHERE item_type=? ORDER BY ts DESC",
        (item_type,)).fetchall()
    return [dict(r) for r in rows]


def unprocessed_count(conn) -> int:
    _ensure_table(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM quick_capture WHERE processed=0").fetchone()
    return r["c"] if r else 0


def search_inbox(conn, query: str) -> list:
    _ensure_table(conn)
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM quick_capture WHERE content LIKE ? ORDER BY ts DESC", (like,)).fetchall()
    return [dict(r) for r in rows]


def total_captured(conn) -> int:
    _ensure_table(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM quick_capture").fetchone()
    return r["c"] if r else 0


def list_types() -> list:
    return list(TYPES)
