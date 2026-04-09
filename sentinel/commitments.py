"""Social commitments — public commitments with deadlines and stakes."""
import time
import datetime as _dt
from . import db


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS commitments (
        id INTEGER PRIMARY KEY, text TEXT, deadline TEXT, stakes TEXT,
        status TEXT DEFAULT 'active', proof TEXT, created_at REAL
    )""")


def create_commitment(conn, text: str, deadline: str, stakes: str = "") -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO commitments (text, deadline, stakes, status, created_at) "
        "VALUES (?, ?, ?, 'active', ?)",
        (text, deadline, stakes, time.time()))
    conn.commit()
    return cur.lastrowid


def get_commitments(conn, status: str = "active") -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM commitments WHERE status=? ORDER BY deadline",
        (status,)).fetchall()
    return [dict(r) for r in rows]


def complete_commitment(conn, commitment_id: int, proof: str = None):
    _ensure_table(conn)
    conn.execute(
        "UPDATE commitments SET status='completed', proof=? WHERE id=?",
        (proof, commitment_id))
    conn.commit()


def fail_commitment(conn, commitment_id: int):
    _ensure_table(conn)
    conn.execute(
        "UPDATE commitments SET status='failed' WHERE id=?", (commitment_id,))
    conn.commit()


def get_commitment(conn, commitment_id: int) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM commitments WHERE id=?", (commitment_id,)).fetchone()
    return dict(r) if r else None


def overdue_commitments(conn) -> list:
    _ensure_table(conn)
    today = _dt.date.today().strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM commitments WHERE status='active' AND deadline < ? "
        "ORDER BY deadline", (today,)).fetchall()
    return [dict(r) for r in rows]
