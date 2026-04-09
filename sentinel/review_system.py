"""GTD-style review system — daily, weekly, monthly, quarterly, annual."""
import time
from datetime import datetime, timedelta


REVIEW_TYPES = ["daily", "weekly", "monthly", "quarterly", "annual"]


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY, review_type TEXT, period_key TEXT,
        reflections TEXT, wins TEXT, struggles TEXT, next_period TEXT,
        completed_at REAL
    )""")


def _period_key(review_type: str) -> str:
    now = datetime.now()
    if review_type == "daily":
        return now.strftime("%Y-%m-%d")
    if review_type == "weekly":
        monday = now.date() - timedelta(days=now.weekday())
        return f"week-{monday.strftime('%Y-%m-%d')}"
    if review_type == "monthly":
        return now.strftime("%Y-%m")
    if review_type == "quarterly":
        q = (now.month - 1) // 3 + 1
        return f"{now.year}-Q{q}"
    if review_type == "annual":
        return str(now.year)
    return ""


def create_review(conn, review_type: str, reflections: str = "",
                  wins: str = "", struggles: str = "", next_period: str = "") -> int:
    _ensure_table(conn)
    if review_type not in REVIEW_TYPES:
        return 0
    period = _period_key(review_type)
    cur = conn.execute(
        """INSERT INTO reviews (review_type, period_key, reflections, wins, struggles, next_period, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (review_type, period, reflections, wins, struggles, next_period, time.time()))
    conn.commit()
    return cur.lastrowid


def get_review(conn, review_id: int) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
    return dict(r) if r else None


def current_review(conn, review_type: str) -> dict:
    _ensure_table(conn)
    period = _period_key(review_type)
    r = conn.execute(
        "SELECT * FROM reviews WHERE review_type=? AND period_key=? ORDER BY completed_at DESC LIMIT 1",
        (review_type, period)).fetchone()
    return dict(r) if r else None


def list_reviews(conn, review_type: str = None, limit: int = 30) -> list:
    _ensure_table(conn)
    if review_type:
        rows = conn.execute(
            "SELECT * FROM reviews WHERE review_type=? ORDER BY completed_at DESC LIMIT ?",
            (review_type, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM reviews ORDER BY completed_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def has_reviewed(conn, review_type: str) -> bool:
    return current_review(conn, review_type) is not None


def delete_review(conn, review_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM reviews WHERE id=?", (review_id,))
    conn.commit()


def overdue_reviews(conn) -> list:
    """Review types that haven't been done this period."""
    out = []
    for rt in REVIEW_TYPES:
        if not has_reviewed(conn, rt):
            out.append(rt)
    return out


def review_streak(conn, review_type: str = "daily") -> int:
    _ensure_table(conn)
    if review_type != "daily":
        return 0
    current = datetime.now().date()
    days = 0
    while True:
        period = current.strftime("%Y-%m-%d")
        r = conn.execute(
            "SELECT 1 FROM reviews WHERE review_type='daily' AND period_key=?", (period,)).fetchone()
        if r:
            days += 1
            current -= timedelta(days=1)
        else:
            if days == 0 and current == datetime.now().date():
                current -= timedelta(days=1)
                continue
            break
    return days


def list_review_types() -> list:
    return list(REVIEW_TYPES)


def total_reviews(conn) -> int:
    _ensure_table(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM reviews").fetchone()
    return r["c"] if r else 0
