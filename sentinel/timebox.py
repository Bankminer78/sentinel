"""Timebox — allocate fixed time windows to specific tasks."""
import time
from datetime import datetime, timedelta


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS timeboxes (
        id INTEGER PRIMARY KEY, task TEXT, planned_minutes INTEGER,
        start_ts REAL, end_ts REAL, actual_minutes REAL, completed INTEGER DEFAULT 0
    )""")


def create_timebox(conn, task: str, minutes: int) -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO timeboxes (task, planned_minutes) VALUES (?, ?)",
        (task, minutes))
    conn.commit()
    return cur.lastrowid


def start_timebox(conn, timebox_id: int):
    _ensure_table(conn)
    conn.execute("UPDATE timeboxes SET start_ts=? WHERE id=?", (time.time(), timebox_id))
    conn.commit()


def end_timebox(conn, timebox_id: int, completed: bool = True):
    _ensure_table(conn)
    now = time.time()
    r = conn.execute("SELECT start_ts FROM timeboxes WHERE id=?", (timebox_id,)).fetchone()
    if r and r["start_ts"]:
        actual = (now - r["start_ts"]) / 60
        conn.execute(
            "UPDATE timeboxes SET end_ts=?, actual_minutes=?, completed=? WHERE id=?",
            (now, actual, 1 if completed else 0, timebox_id))
    else:
        conn.execute(
            "UPDATE timeboxes SET end_ts=?, completed=? WHERE id=?",
            (now, 1 if completed else 0, timebox_id))
    conn.commit()


def get_timebox(conn, timebox_id: int) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM timeboxes WHERE id=?", (timebox_id,)).fetchone()
    return dict(r) if r else None


def list_timeboxes(conn, days: int = 7) -> list:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT * FROM timeboxes WHERE COALESCE(start_ts, 0) > ? OR end_ts > ? ORDER BY id DESC",
        (cutoff, cutoff)).fetchall()
    return [dict(r) for r in rows]


def active_timebox(conn) -> dict:
    _ensure_table(conn)
    r = conn.execute(
        "SELECT * FROM timeboxes WHERE start_ts IS NOT NULL AND end_ts IS NULL LIMIT 1"
    ).fetchone()
    return dict(r) if r else None


def delete_timebox(conn, timebox_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM timeboxes WHERE id=?", (timebox_id,))
    conn.commit()


def estimate_accuracy(conn, days: int = 30) -> float:
    """How accurate are your estimates? Returns avg ratio of actual/planned."""
    _ensure_table(conn)
    rows = conn.execute("""SELECT planned_minutes, actual_minutes FROM timeboxes
                            WHERE actual_minutes IS NOT NULL AND planned_minutes > 0""").fetchall()
    if not rows:
        return 0
    ratios = [r["actual_minutes"] / r["planned_minutes"] for r in rows]
    return round(sum(ratios) / len(ratios), 2)


def completion_rate(conn, days: int = 7) -> float:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    total = conn.execute(
        "SELECT COUNT(*) as c FROM timeboxes WHERE COALESCE(start_ts, 0) > ?",
        (cutoff,)).fetchone()["c"]
    if total == 0:
        return 0
    done = conn.execute(
        "SELECT COUNT(*) as c FROM timeboxes WHERE completed=1 AND COALESCE(start_ts, 0) > ?",
        (cutoff,)).fetchone()["c"]
    return round(done / total * 100, 1)
