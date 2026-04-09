"""Subscription tracker — track recurring subscriptions to cancel waste."""
import time
from datetime import datetime, timedelta


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY, name TEXT, amount REAL, frequency TEXT,
        renewal_date TEXT, category TEXT, active INTEGER DEFAULT 1,
        last_used TEXT, added_at REAL
    )""")


def add_subscription(conn, name: str, amount: float, frequency: str = "monthly",
                     renewal_date: str = None, category: str = "") -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO subscriptions (name, amount, frequency, renewal_date, category, added_at) VALUES (?, ?, ?, ?, ?, ?)",
        (name, amount, frequency, renewal_date, category, time.time()))
    conn.commit()
    return cur.lastrowid


def get_subscriptions(conn, active_only: bool = True) -> list:
    _ensure_table(conn)
    q = "SELECT * FROM subscriptions"
    if active_only:
        q += " WHERE active=1"
    rows = conn.execute(q).fetchall()
    return [dict(r) for r in rows]


def cancel_subscription(conn, subscription_id: int):
    _ensure_table(conn)
    conn.execute("UPDATE subscriptions SET active=0 WHERE id=?", (subscription_id,))
    conn.commit()


def delete_subscription(conn, subscription_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM subscriptions WHERE id=?", (subscription_id,))
    conn.commit()


def monthly_total(conn) -> float:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT amount, frequency FROM subscriptions WHERE active=1").fetchall()
    total = 0
    for r in rows:
        amount = r["amount"]
        freq = r["frequency"]
        if freq == "monthly":
            total += amount
        elif freq == "yearly":
            total += amount / 12
        elif freq == "weekly":
            total += amount * 4.33
        elif freq == "quarterly":
            total += amount / 3
    return round(total, 2)


def yearly_total(conn) -> float:
    return round(monthly_total(conn) * 12, 2)


def renewing_soon(conn, days: int = 7) -> list:
    _ensure_table(conn)
    cutoff = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM subscriptions WHERE active=1 AND renewal_date BETWEEN ? AND ?",
        (today, cutoff)).fetchall()
    return [dict(r) for r in rows]


def mark_used(conn, subscription_id: int):
    _ensure_table(conn)
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute("UPDATE subscriptions SET last_used=? WHERE id=?", (today, subscription_id))
    conn.commit()


def unused_subscriptions(conn, days: int = 30) -> list:
    """Subscriptions not used in the last N days."""
    _ensure_table(conn)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM subscriptions WHERE active=1 AND (last_used IS NULL OR last_used < ?)",
        (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def by_category(conn) -> dict:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT category, COUNT(*) as count, SUM(amount) as total FROM subscriptions WHERE active=1 GROUP BY category"
    ).fetchall()
    return {r["category"] or "uncategorized": {"count": r["count"], "total": round(r["total"], 2)}
            for r in rows}
