"""Simple money tracker — track spending to tie accountability to finances."""
import time
from datetime import datetime, timedelta


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY, amount REAL, category TEXT, description TEXT,
        date TEXT, ts REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS expense_budgets (
        id INTEGER PRIMARY KEY, category TEXT UNIQUE, monthly_limit REAL
    )""")


def log_expense(conn, amount: float, category: str, description: str = "") -> int:
    _ensure_tables(conn)
    date_str = datetime.now().strftime("%Y-%m-%d")
    cur = conn.execute(
        "INSERT INTO expenses (amount, category, description, date, ts) VALUES (?, ?, ?, ?, ?)",
        (amount, category, description, date_str, time.time()))
    conn.commit()
    return cur.lastrowid


def get_expenses(conn, category: str = None, days: int = 30) -> list:
    _ensure_tables(conn)
    cutoff = time.time() - days * 86400
    q = "SELECT * FROM expenses WHERE ts > ?"
    params = [cutoff]
    if category:
        q += " AND category=?"
        params.append(category)
    q += " ORDER BY ts DESC"
    rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def total_spent(conn, category: str = None, days: int = 30) -> float:
    _ensure_tables(conn)
    cutoff = time.time() - days * 86400
    q = "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE ts > ?"
    params = [cutoff]
    if category:
        q += " AND category=?"
        params.append(category)
    r = conn.execute(q, params).fetchone()
    return round(r["total"] or 0, 2)


def spending_by_category(conn, days: int = 30) -> dict:
    _ensure_tables(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT category, SUM(amount) as total FROM expenses WHERE ts > ? GROUP BY category",
        (cutoff,)).fetchall()
    return {r["category"]: round(r["total"], 2) for r in rows}


def set_budget(conn, category: str, monthly_limit: float) -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT OR REPLACE INTO expense_budgets (category, monthly_limit) VALUES (?, ?)",
        (category, monthly_limit))
    conn.commit()
    return cur.lastrowid


def get_budgets(conn) -> list:
    _ensure_tables(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM expense_budgets").fetchall()]


def budget_status(conn, category: str) -> dict:
    _ensure_tables(conn)
    r = conn.execute(
        "SELECT * FROM expense_budgets WHERE category=?", (category,)).fetchone()
    if not r:
        return None
    spent = total_spent(conn, category=category, days=30)
    limit = r["monthly_limit"]
    return {
        "category": category,
        "limit": limit,
        "spent": spent,
        "remaining": max(0, limit - spent),
        "exceeded": spent > limit,
        "percent": round((spent / limit * 100) if limit > 0 else 0, 1),
    }


def delete_expense(conn, expense_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    conn.commit()


def biggest_expenses(conn, days: int = 30, limit: int = 10) -> list:
    _ensure_tables(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT * FROM expenses WHERE ts > ? ORDER BY amount DESC LIMIT ?",
        (cutoff, limit)).fetchall()
    return [dict(r) for r in rows]
