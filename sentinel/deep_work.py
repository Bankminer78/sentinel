"""Deep work tracker — specifically track flow state sessions."""
import time
from datetime import datetime, timedelta


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS deep_work_sessions (
        id INTEGER PRIMARY KEY, start_ts REAL, end_ts REAL,
        project TEXT, quality INTEGER, notes TEXT
    )""")


def start_deep_work(conn, project: str = "") -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO deep_work_sessions (start_ts, project) VALUES (?, ?)",
        (time.time(), project))
    conn.commit()
    return cur.lastrowid


def end_deep_work(conn, session_id: int, quality: int = None, notes: str = "") -> dict:
    _ensure_table(conn)
    now = time.time()
    conn.execute(
        "UPDATE deep_work_sessions SET end_ts=?, quality=?, notes=? WHERE id=?",
        (now, quality, notes, session_id))
    conn.commit()
    r = conn.execute("SELECT * FROM deep_work_sessions WHERE id=?", (session_id,)).fetchone()
    return dict(r) if r else {}


def get_active_session(conn) -> dict:
    _ensure_table(conn)
    r = conn.execute(
        "SELECT * FROM deep_work_sessions WHERE end_ts IS NULL ORDER BY start_ts DESC LIMIT 1"
    ).fetchone()
    return dict(r) if r else None


def get_sessions(conn, days: int = 30) -> list:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT * FROM deep_work_sessions WHERE start_ts > ? ORDER BY start_ts DESC",
        (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def total_hours(conn, days: int = 7) -> float:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute("""SELECT COALESCE(SUM(end_ts - start_ts), 0) as total
                        FROM deep_work_sessions WHERE end_ts IS NOT NULL AND start_ts > ?""",
                     (cutoff,)).fetchone()
    return round((r["total"] or 0) / 3600, 1)


def avg_session_length(conn, days: int = 30) -> float:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute("""SELECT AVG(end_ts - start_ts) as avg FROM deep_work_sessions
                        WHERE end_ts IS NOT NULL AND start_ts > ?""", (cutoff,)).fetchone()
    return round((r["avg"] or 0) / 60, 1)  # minutes


def longest_session(conn, days: int = 30) -> float:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute("""SELECT MAX(end_ts - start_ts) as longest FROM deep_work_sessions
                        WHERE end_ts IS NOT NULL AND start_ts > ?""", (cutoff,)).fetchone()
    return round((r["longest"] or 0) / 60, 1)  # minutes


def quality_average(conn, days: int = 30) -> float:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute("""SELECT AVG(quality) as avg FROM deep_work_sessions
                        WHERE quality IS NOT NULL AND start_ts > ?""", (cutoff,)).fetchone()
    return round(r["avg"] or 0, 1)


def by_project(conn, days: int = 30) -> dict:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute("""SELECT project, COUNT(*) as sessions,
                           COALESCE(SUM(end_ts - start_ts), 0) as total_seconds
                           FROM deep_work_sessions
                           WHERE end_ts IS NOT NULL AND start_ts > ?
                           GROUP BY project""", (cutoff,)).fetchall()
    return {r["project"] or "untagged": {"sessions": r["sessions"],
                                           "total_seconds": r["total_seconds"]} for r in rows}
