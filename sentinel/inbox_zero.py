"""Inbox Zero tracker — track email inbox counts."""
import time
from datetime import datetime, timedelta


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS inbox_counts (
        id INTEGER PRIMARY KEY, email_account TEXT, unread INTEGER,
        inbox_total INTEGER, ts REAL
    )""")


def log_count(conn, account: str, unread: int, total: int = 0) -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO inbox_counts (email_account, unread, inbox_total, ts) VALUES (?, ?, ?, ?)",
        (account, unread, total, time.time()))
    conn.commit()
    return cur.lastrowid


def current_count(conn, account: str) -> dict:
    _ensure_table(conn)
    r = conn.execute(
        "SELECT * FROM inbox_counts WHERE email_account=? ORDER BY ts DESC LIMIT 1",
        (account,)).fetchone()
    return dict(r) if r else None


def is_at_zero(conn, account: str) -> bool:
    current = current_count(conn, account)
    return current is not None and current["unread"] == 0


def zero_streak(conn, account: str) -> int:
    """Consecutive days at inbox zero."""
    _ensure_table(conn)
    current = datetime.now().date()
    days = 0
    while True:
        day_start = datetime.combine(current, datetime.min.time()).timestamp()
        day_end = day_start + 86400
        r = conn.execute(
            "SELECT MIN(unread) as min_unread FROM inbox_counts WHERE email_account=? AND ts >= ? AND ts < ?",
            (account, day_start, day_end)).fetchone()
        if r and r["min_unread"] == 0:
            days += 1
            current -= timedelta(days=1)
        else:
            break
    return days


def get_history(conn, account: str, days: int = 30) -> list:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT * FROM inbox_counts WHERE email_account=? AND ts > ? ORDER BY ts",
        (account, cutoff)).fetchall()
    return [dict(r) for r in rows]


def avg_unread(conn, account: str, days: int = 7) -> float:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute(
        "SELECT AVG(unread) as avg FROM inbox_counts WHERE email_account=? AND ts > ?",
        (account, cutoff)).fetchone()
    return round(r["avg"] or 0, 1)


def list_accounts(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT DISTINCT email_account FROM inbox_counts"
    ).fetchall()
    return [r["email_account"] for r in rows]


def times_at_zero(conn, account: str, days: int = 30) -> int:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute(
        "SELECT COUNT(*) as c FROM inbox_counts WHERE email_account=? AND ts > ? AND unread=0",
        (account, cutoff)).fetchone()
    return r["c"] if r else 0


def trend(conn, account: str, days: int = 14) -> str:
    counts = get_history(conn, account, days)
    if len(counts) < 4:
        return "stable"
    mid = len(counts) // 2
    first = sum(c["unread"] for c in counts[:mid]) / mid
    second = sum(c["unread"] for c in counts[mid:]) / (len(counts) - mid)
    if second < first - 3:
        return "improving"
    if second > first + 3:
        return "worsening"
    return "stable"
