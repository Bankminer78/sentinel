"""Daily learnings log — capture what you learned each day."""
import time
from datetime import datetime, timedelta


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS learnings (
        id INTEGER PRIMARY KEY, content TEXT, category TEXT,
        source TEXT, date TEXT, ts REAL
    )""")


def add_learning(conn, content: str, category: str = "general", source: str = "") -> int:
    _ensure_table(conn)
    date_str = datetime.now().strftime("%Y-%m-%d")
    cur = conn.execute(
        "INSERT INTO learnings (content, category, source, date, ts) VALUES (?, ?, ?, ?, ?)",
        (content, category, source, date_str, time.time()))
    conn.commit()
    return cur.lastrowid


def get_learnings(conn, date_str: str = None, category: str = None, limit: int = 50) -> list:
    _ensure_table(conn)
    q = "SELECT * FROM learnings WHERE 1=1"
    params = []
    if date_str:
        q += " AND date=?"
        params.append(date_str)
    if category:
        q += " AND category=?"
        params.append(category)
    q += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def today_learnings(conn) -> list:
    return get_learnings(conn, date_str=datetime.now().strftime("%Y-%m-%d"))


def weekly_learnings(conn) -> list:
    _ensure_table(conn)
    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM learnings WHERE date >= ? ORDER BY ts DESC",
        (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def delete_learning(conn, learning_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM learnings WHERE id=?", (learning_id,))
    conn.commit()


def search_learnings(conn, query: str) -> list:
    _ensure_table(conn)
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM learnings WHERE content LIKE ? ORDER BY ts DESC", (like,)).fetchall()
    return [dict(r) for r in rows]


def count_by_category(conn, days: int = 30) -> dict:
    _ensure_table(conn)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT category, COUNT(*) as c FROM learnings WHERE date >= ? GROUP BY category",
        (cutoff,)).fetchall()
    return {r["category"]: r["c"] for r in rows}


def learning_streak(conn) -> int:
    _ensure_table(conn)
    current = datetime.now().date()
    days = 0
    while True:
        dstr = current.strftime("%Y-%m-%d")
        r = conn.execute("SELECT COUNT(*) as c FROM learnings WHERE date=?", (dstr,)).fetchone()
        if r["c"] > 0:
            days += 1
            current -= timedelta(days=1)
        else:
            if days == 0 and current == datetime.now().date():
                current -= timedelta(days=1)
                continue
            break
    return days


def total_learnings(conn) -> int:
    _ensure_table(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM learnings").fetchone()
    return r["c"] if r else 0
