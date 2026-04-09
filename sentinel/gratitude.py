"""Gratitude journal — daily things to be thankful for."""
import time
from datetime import datetime, timedelta


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS gratitude (
        id INTEGER PRIMARY KEY, text TEXT, date TEXT, ts REAL
    )""")


def add_gratitude(conn, text: str, date_str: str = None) -> int:
    _ensure_table(conn)
    d = date_str or datetime.now().strftime("%Y-%m-%d")
    cur = conn.execute(
        "INSERT INTO gratitude (text, date, ts) VALUES (?, ?, ?)",
        (text, d, time.time()))
    conn.commit()
    return cur.lastrowid


def get_gratitudes(conn, date_str: str = None) -> list:
    _ensure_table(conn)
    if date_str:
        rows = conn.execute(
            "SELECT * FROM gratitude WHERE date=? ORDER BY ts DESC", (date_str,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM gratitude ORDER BY ts DESC LIMIT 100").fetchall()
    return [dict(r) for r in rows]


def today_gratitudes(conn) -> list:
    today = datetime.now().strftime("%Y-%m-%d")
    return get_gratitudes(conn, today)


def delete_gratitude(conn, gratitude_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM gratitude WHERE id=?", (gratitude_id,))
    conn.commit()


def gratitude_streak(conn) -> int:
    """Consecutive days with at least one gratitude entry."""
    _ensure_table(conn)
    current = datetime.now().date()
    days = 0
    while True:
        dstr = current.strftime("%Y-%m-%d")
        r = conn.execute("SELECT COUNT(*) as c FROM gratitude WHERE date=?", (dstr,)).fetchone()
        if r["c"] > 0:
            days += 1
            current -= timedelta(days=1)
        else:
            if days == 0 and current == datetime.now().date():
                current -= timedelta(days=1)
                continue
            break
    return days


def search_gratitudes(conn, query: str) -> list:
    _ensure_table(conn)
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM gratitude WHERE text LIKE ? ORDER BY ts DESC", (like,)).fetchall()
    return [dict(r) for r in rows]


def count_gratitudes(conn, days: int = 30) -> int:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute("SELECT COUNT(*) as c FROM gratitude WHERE ts > ?", (cutoff,)).fetchone()
    return r["c"]


def random_gratitude(conn) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM gratitude ORDER BY RANDOM() LIMIT 1").fetchone()
    return dict(r) if r else None
