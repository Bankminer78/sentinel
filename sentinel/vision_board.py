"""Vision board — aspirational images/quotes for motivation."""
import time, json


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS vision_board (
        id INTEGER PRIMARY KEY, type TEXT, content TEXT, url TEXT,
        category TEXT, priority INTEGER DEFAULT 0, added_at REAL
    )""")


ITEM_TYPES = ["quote", "image", "goal", "affirmation", "person", "place", "thing"]


def add_item(conn, item_type: str, content: str, url: str = "",
             category: str = "", priority: int = 0) -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO vision_board (type, content, url, category, priority, added_at) VALUES (?, ?, ?, ?, ?, ?)",
        (item_type, content, url, category, priority, time.time()))
    conn.commit()
    return cur.lastrowid


def get_items(conn, item_type: str = None, category: str = None) -> list:
    _ensure_table(conn)
    q = "SELECT * FROM vision_board WHERE 1=1"
    params = []
    if item_type:
        q += " AND type=?"
        params.append(item_type)
    if category:
        q += " AND category=?"
        params.append(category)
    q += " ORDER BY priority DESC, added_at DESC"
    rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def get_item(conn, item_id: int) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM vision_board WHERE id=?", (item_id,)).fetchone()
    return dict(r) if r else None


def delete_item(conn, item_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM vision_board WHERE id=?", (item_id,))
    conn.commit()


def update_priority(conn, item_id: int, priority: int):
    _ensure_table(conn)
    conn.execute("UPDATE vision_board SET priority=? WHERE id=?", (priority, item_id))
    conn.commit()


def top_items(conn, limit: int = 10) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM vision_board ORDER BY priority DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def random_affirmation(conn) -> dict:
    _ensure_table(conn)
    r = conn.execute(
        "SELECT * FROM vision_board WHERE type='affirmation' ORDER BY RANDOM() LIMIT 1"
    ).fetchone()
    return dict(r) if r else None


def categories(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT DISTINCT category, COUNT(*) as c FROM vision_board WHERE category != '' GROUP BY category"
    ).fetchall()
    return [dict(r) for r in rows]


def count_items(conn) -> int:
    _ensure_table(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM vision_board").fetchone()
    return r["c"] if r else 0


def list_item_types() -> list:
    return list(ITEM_TYPES)
