"""Mentor mode — mentor or be mentored by another user."""
import time


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS mentorships (
        id INTEGER PRIMARY KEY, mentor_name TEXT, mentee_name TEXT,
        topic TEXT, started_at REAL, active INTEGER DEFAULT 1
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS mentorship_sessions (
        id INTEGER PRIMARY KEY, mentorship_id INTEGER, notes TEXT,
        action_items TEXT, session_date TEXT, ts REAL
    )""")


def start_mentorship(conn, mentor_name: str, mentee_name: str, topic: str = "") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO mentorships (mentor_name, mentee_name, topic, started_at) VALUES (?, ?, ?, ?)",
        (mentor_name, mentee_name, topic, time.time()))
    conn.commit()
    return cur.lastrowid


def get_mentorships(conn, as_mentor: str = None, as_mentee: str = None) -> list:
    _ensure_tables(conn)
    if as_mentor:
        rows = conn.execute(
            "SELECT * FROM mentorships WHERE mentor_name=? AND active=1",
            (as_mentor,)).fetchall()
    elif as_mentee:
        rows = conn.execute(
            "SELECT * FROM mentorships WHERE mentee_name=? AND active=1",
            (as_mentee,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM mentorships WHERE active=1").fetchall()
    return [dict(r) for r in rows]


def end_mentorship(conn, mentorship_id: int):
    _ensure_tables(conn)
    conn.execute("UPDATE mentorships SET active=0 WHERE id=?", (mentorship_id,))
    conn.commit()


def log_session(conn, mentorship_id: int, notes: str, action_items: str = "",
                session_date: str = None) -> int:
    _ensure_tables(conn)
    from datetime import datetime
    d = session_date or datetime.now().strftime("%Y-%m-%d")
    cur = conn.execute(
        "INSERT INTO mentorship_sessions (mentorship_id, notes, action_items, session_date, ts) VALUES (?, ?, ?, ?, ?)",
        (mentorship_id, notes, action_items, d, time.time()))
    conn.commit()
    return cur.lastrowid


def get_sessions(conn, mentorship_id: int) -> list:
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT * FROM mentorship_sessions WHERE mentorship_id=? ORDER BY ts DESC",
        (mentorship_id,)).fetchall()
    return [dict(r) for r in rows]


def delete_session(conn, session_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM mentorship_sessions WHERE id=?", (session_id,))
    conn.commit()


def mentorship_summary(conn, mentorship_id: int) -> dict:
    _ensure_tables(conn)
    r = conn.execute("SELECT * FROM mentorships WHERE id=?", (mentorship_id,)).fetchone()
    if not r:
        return None
    sessions = get_sessions(conn, mentorship_id)
    return {
        **dict(r),
        "session_count": len(sessions),
        "last_session": sessions[0] if sessions else None,
    }


def total_active(conn) -> int:
    _ensure_tables(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM mentorships WHERE active=1").fetchone()
    return r["c"]
