"""Financial penalties — tracks $$ owed per rule violation."""
import time


def add_penalty_rule(conn, rule_id: int, amount_usd: float) -> int:
    conn.execute(
        "INSERT OR REPLACE INTO penalty_rules (rule_id, amount) VALUES (?,?)",
        (rule_id, amount_usd))
    conn.commit()
    return rule_id


def get_penalty_rule(conn, rule_id: int) -> float | None:
    r = conn.execute(
        "SELECT amount FROM penalty_rules WHERE rule_id=?", (rule_id,)).fetchone()
    return r["amount"] if r else None


def remove_penalty_rule(conn, rule_id: int) -> None:
    conn.execute("DELETE FROM penalty_rules WHERE rule_id=?", (rule_id,))
    conn.commit()


def record_violation(conn, rule_id: int, amount_usd: float | None = None) -> int:
    if amount_usd is None:
        amount_usd = get_penalty_rule(conn, rule_id) or 0.0
    cur = conn.execute(
        "INSERT INTO penalties (rule_id, amount, created_at, paid) VALUES (?,?,?,0)",
        (rule_id, amount_usd, time.time()))
    conn.commit()
    return cur.lastrowid


def get_pending_penalties(conn) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM penalties WHERE paid=0 ORDER BY created_at DESC").fetchall()]


def get_all_penalties(conn) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM penalties ORDER BY created_at DESC").fetchall()]


def mark_penalty_paid(conn, penalty_id: int) -> None:
    conn.execute("UPDATE penalties SET paid=1 WHERE id=?", (penalty_id,))
    conn.commit()


def total_owed(conn) -> float:
    r = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS t FROM penalties WHERE paid=0").fetchone()
    return float(r["t"] or 0.0)


def total_paid(conn) -> float:
    r = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS t FROM penalties WHERE paid=1").fetchone()
    return float(r["t"] or 0.0)
