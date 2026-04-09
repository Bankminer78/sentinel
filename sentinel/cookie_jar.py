"""Cookie jar — positive reinforcement jar. Record wins to re-read later."""
import time
import random


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS cookie_jar (
        id INTEGER PRIMARY KEY, content TEXT, category TEXT,
        date TEXT, ts REAL
    )""")


def add_cookie(conn, content: str, category: str = "win") -> int:
    _ensure_table(conn)
    from datetime import datetime
    date_str = datetime.now().strftime("%Y-%m-%d")
    cur = conn.execute(
        "INSERT INTO cookie_jar (content, category, date, ts) VALUES (?, ?, ?, ?)",
        (content, category, date_str, time.time()))
    conn.commit()
    return cur.lastrowid


def get_cookies(conn, category: str = None, limit: int = 100) -> list:
    _ensure_table(conn)
    if category:
        rows = conn.execute(
            "SELECT * FROM cookie_jar WHERE category=? ORDER BY ts DESC LIMIT ?",
            (category, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM cookie_jar ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def random_cookie(conn, category: str = None) -> dict:
    _ensure_table(conn)
    if category:
        r = conn.execute(
            "SELECT * FROM cookie_jar WHERE category=? ORDER BY RANDOM() LIMIT 1",
            (category,)).fetchone()
    else:
        r = conn.execute("SELECT * FROM cookie_jar ORDER BY RANDOM() LIMIT 1").fetchone()
    return dict(r) if r else None


def delete_cookie(conn, cookie_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM cookie_jar WHERE id=?", (cookie_id,))
    conn.commit()


def count_cookies(conn, category: str = None) -> int:
    _ensure_table(conn)
    if category:
        r = conn.execute(
            "SELECT COUNT(*) as c FROM cookie_jar WHERE category=?", (category,)).fetchone()
    else:
        r = conn.execute("SELECT COUNT(*) as c FROM cookie_jar").fetchone()
    return r["c"] if r else 0


def categories(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT DISTINCT category, COUNT(*) as count FROM cookie_jar GROUP BY category"
    ).fetchall()
    return [dict(r) for r in rows]


def search_cookies(conn, query: str) -> list:
    _ensure_table(conn)
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM cookie_jar WHERE content LIKE ? ORDER BY ts DESC", (like,)).fetchall()
    return [dict(r) for r in rows]


def cookies_this_month(conn) -> int:
    _ensure_table(conn)
    from datetime import datetime
    this_month = datetime.now().strftime("%Y-%m")
    r = conn.execute(
        "SELECT COUNT(*) as c FROM cookie_jar WHERE date LIKE ?",
        (f"{this_month}%",)).fetchone()
    return r["c"] if r else 0


def oldest_cookie(conn) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM cookie_jar ORDER BY ts ASC LIMIT 1").fetchone()
    return dict(r) if r else None


def jar_summary(conn) -> dict:
    return {
        "total": count_cookies(conn),
        "wins": count_cookies(conn, "win"),
        "gratitude": count_cookies(conn, "gratitude"),
        "compliment": count_cookies(conn, "compliment"),
        "this_month": cookies_this_month(conn),
    }
