"""Future self letters — write letters to your future self."""
import time
from datetime import datetime, timedelta


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS future_letters (
        id INTEGER PRIMARY KEY, content TEXT, delivery_date TEXT,
        created_at REAL, delivered INTEGER DEFAULT 0, opened_at REAL
    )""")


def write_letter(conn, content: str, deliver_in_days: int = 30) -> int:
    _ensure_table(conn)
    delivery = (datetime.now() + timedelta(days=deliver_in_days)).strftime("%Y-%m-%d")
    cur = conn.execute(
        "INSERT INTO future_letters (content, delivery_date, created_at) VALUES (?, ?, ?)",
        (content, delivery, time.time()))
    conn.commit()
    return cur.lastrowid


def get_letter(conn, letter_id: int) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM future_letters WHERE id=?", (letter_id,)).fetchone()
    return dict(r) if r else None


def list_letters(conn, delivered: bool = None) -> list:
    _ensure_table(conn)
    q = "SELECT * FROM future_letters"
    if delivered is not None:
        q += f" WHERE delivered={1 if delivered else 0}"
    q += " ORDER BY delivery_date"
    rows = conn.execute(q).fetchall()
    return [dict(r) for r in rows]


def deliverable_today(conn) -> list:
    """Letters whose delivery date has arrived and haven't been opened."""
    _ensure_table(conn)
    today = datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM future_letters WHERE delivery_date <= ? AND delivered=0",
        (today,)).fetchall()
    return [dict(r) for r in rows]


def open_letter(conn, letter_id: int) -> dict:
    _ensure_table(conn)
    conn.execute(
        "UPDATE future_letters SET delivered=1, opened_at=? WHERE id=?",
        (time.time(), letter_id))
    conn.commit()
    return get_letter(conn, letter_id)


def delete_letter(conn, letter_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM future_letters WHERE id=?", (letter_id,))
    conn.commit()


def pending_letters(conn) -> list:
    return list_letters(conn, delivered=False)


def opened_letters(conn) -> list:
    return list_letters(conn, delivered=True)


def count_pending(conn) -> int:
    _ensure_table(conn)
    r = conn.execute(
        "SELECT COUNT(*) as c FROM future_letters WHERE delivered=0").fetchone()
    return r["c"] if r else 0


def days_until_delivery(conn, letter_id: int) -> int:
    letter = get_letter(conn, letter_id)
    if not letter or not letter.get("delivery_date"):
        return 0
    delivery = datetime.strptime(letter["delivery_date"], "%Y-%m-%d").date()
    today = datetime.now().date()
    return max(0, (delivery - today).days)
