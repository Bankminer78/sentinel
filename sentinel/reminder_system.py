"""Generic reminder system — schedule and trigger reminders."""
import time, json
from datetime import datetime, timedelta


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY, title TEXT, message TEXT,
        trigger_at REAL, recurring TEXT, notified INTEGER DEFAULT 0,
        created_at REAL
    )""")


def create_reminder(conn, title: str, message: str = "", trigger_at: float = None,
                    recurring: str = "") -> int:
    _ensure_table(conn)
    if trigger_at is None:
        trigger_at = time.time() + 3600  # 1 hour default
    cur = conn.execute(
        """INSERT INTO reminders (title, message, trigger_at, recurring, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (title, message, trigger_at, recurring, time.time()))
    conn.commit()
    return cur.lastrowid


def get_reminder(conn, reminder_id: int) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM reminders WHERE id=?", (reminder_id,)).fetchone()
    return dict(r) if r else None


def list_reminders(conn, pending_only: bool = False) -> list:
    _ensure_table(conn)
    q = "SELECT * FROM reminders"
    if pending_only:
        q += " WHERE notified=0"
    q += " ORDER BY trigger_at"
    rows = conn.execute(q).fetchall()
    return [dict(r) for r in rows]


def due_reminders(conn) -> list:
    _ensure_table(conn)
    now = time.time()
    rows = conn.execute(
        "SELECT * FROM reminders WHERE notified=0 AND trigger_at <= ?", (now,)).fetchall()
    return [dict(r) for r in rows]


def mark_notified(conn, reminder_id: int):
    _ensure_table(conn)
    r = get_reminder(conn, reminder_id)
    if not r:
        return
    conn.execute("UPDATE reminders SET notified=1 WHERE id=?", (reminder_id,))
    # If recurring, create next one
    if r.get("recurring"):
        next_trigger = _next_trigger(r["trigger_at"], r["recurring"])
        if next_trigger:
            create_reminder(conn, r["title"], r["message"], next_trigger, r["recurring"])
    conn.commit()


def _next_trigger(current: float, recurring: str) -> float:
    if recurring == "daily":
        return current + 86400
    if recurring == "weekly":
        return current + 604800
    if recurring == "hourly":
        return current + 3600
    if recurring == "monthly":
        return current + 2592000
    return None


def delete_reminder(conn, reminder_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
    conn.commit()


def reschedule(conn, reminder_id: int, new_trigger: float):
    _ensure_table(conn)
    conn.execute(
        "UPDATE reminders SET trigger_at=?, notified=0 WHERE id=?",
        (new_trigger, reminder_id))
    conn.commit()


def snooze(conn, reminder_id: int, minutes: int):
    r = get_reminder(conn, reminder_id)
    if not r:
        return
    new_trigger = time.time() + minutes * 60
    reschedule(conn, reminder_id, new_trigger)


def upcoming(conn, hours: int = 24) -> list:
    _ensure_table(conn)
    now = time.time()
    cutoff = now + hours * 3600
    rows = conn.execute(
        "SELECT * FROM reminders WHERE notified=0 AND trigger_at BETWEEN ? AND ? ORDER BY trigger_at",
        (now, cutoff)).fetchall()
    return [dict(r) for r in rows]


def total_reminders(conn) -> int:
    _ensure_table(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM reminders").fetchone()
    return r["c"] if r else 0
