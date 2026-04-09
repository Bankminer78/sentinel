"""Morning Pages — Julia Cameron-style daily stream of consciousness writing."""
import time
from datetime import datetime, timedelta


TARGET_WORDS = 750  # ~3 pages


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS morning_pages (
        date TEXT PRIMARY KEY, content TEXT, word_count INTEGER,
        duration_min INTEGER, ts REAL
    )""")


def write_pages(conn, content: str, duration_min: int = 0, date_str: str = None) -> dict:
    _ensure_table(conn)
    d = date_str or datetime.now().strftime("%Y-%m-%d")
    words = len([w for w in content.split() if w])
    conn.execute(
        """INSERT OR REPLACE INTO morning_pages
           (date, content, word_count, duration_min, ts) VALUES (?, ?, ?, ?, ?)""",
        (d, content, words, duration_min, time.time()))
    conn.commit()
    return {"date": d, "word_count": words, "target": TARGET_WORDS, "met": words >= TARGET_WORDS}


def get_pages(conn, date_str: str = None) -> dict:
    _ensure_table(conn)
    d = date_str or datetime.now().strftime("%Y-%m-%d")
    r = conn.execute("SELECT * FROM morning_pages WHERE date=?", (d,)).fetchone()
    return dict(r) if r else None


def list_recent(conn, limit: int = 14) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM morning_pages ORDER BY date DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def streak(conn) -> int:
    _ensure_table(conn)
    current = datetime.now().date()
    days = 0
    while True:
        dstr = current.strftime("%Y-%m-%d")
        r = conn.execute("SELECT word_count FROM morning_pages WHERE date=?", (dstr,)).fetchone()
        if r and r["word_count"] >= 100:
            days += 1
            current -= timedelta(days=1)
        else:
            if days == 0 and current == datetime.now().date():
                current -= timedelta(days=1)
                continue
            break
    return days


def total_words(conn, days: int = 30) -> int:
    _ensure_table(conn)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    r = conn.execute(
        "SELECT COALESCE(SUM(word_count), 0) as total FROM morning_pages WHERE date >= ?",
        (cutoff,)).fetchone()
    return r["total"] or 0


def avg_words(conn, days: int = 30) -> float:
    _ensure_table(conn)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT word_count FROM morning_pages WHERE date >= ?", (cutoff,)).fetchall()
    if not rows:
        return 0
    return round(sum(r["word_count"] for r in rows) / len(rows), 1)


def target_met_days(conn, days: int = 30) -> int:
    _ensure_table(conn)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    r = conn.execute(
        "SELECT COUNT(*) as c FROM morning_pages WHERE date >= ? AND word_count >= ?",
        (cutoff, TARGET_WORDS)).fetchone()
    return r["c"] if r else 0


def search_pages(conn, query: str) -> list:
    _ensure_table(conn)
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM morning_pages WHERE content LIKE ? ORDER BY date DESC",
        (like,)).fetchall()
    return [dict(r) for r in rows]


def delete_pages(conn, date_str: str):
    _ensure_table(conn)
    conn.execute("DELETE FROM morning_pages WHERE date=?", (date_str,))
    conn.commit()


def total_count(conn) -> int:
    _ensure_table(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM morning_pages").fetchone()
    return r["c"] if r else 0
