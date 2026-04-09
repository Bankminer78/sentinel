"""Manual time tracking — like Toggl/RescueTime."""
import time
from datetime import datetime


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS time_entries (
        id INTEGER PRIMARY KEY, project TEXT, description TEXT,
        start_ts REAL, end_ts REAL, duration_s REAL
    )""")


def start_tracking(conn, project: str, description: str = "") -> int:
    _ensure_table(conn)
    # Stop any active tracking first
    active = get_active_tracking(conn)
    if active:
        stop_tracking(conn, active["id"])
    cur = conn.execute("INSERT INTO time_entries (project, description, start_ts) VALUES (?, ?, ?)",
                       (project, description, time.time()))
    conn.commit()
    return cur.lastrowid


def stop_tracking(conn, session_id: int = None) -> dict:
    _ensure_table(conn)
    active = get_active_tracking(conn) if session_id is None else None
    sid = session_id if session_id is not None else (active["id"] if active else None)
    if sid is None:
        return None
    now = time.time()
    conn.execute("""UPDATE time_entries SET end_ts=?,
                    duration_s=? - start_ts WHERE id=? AND end_ts IS NULL""",
                 (now, now, sid))
    conn.commit()
    r = conn.execute("SELECT * FROM time_entries WHERE id=?", (sid,)).fetchone()
    return dict(r) if r else None


def get_active_tracking(conn) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM time_entries WHERE end_ts IS NULL ORDER BY start_ts DESC LIMIT 1").fetchone()
    return dict(r) if r else None


def get_tracked_time(conn, project: str = None, date_str: str = None) -> dict:
    _ensure_table(conn)
    q = "SELECT project, SUM(duration_s) as total FROM time_entries WHERE end_ts IS NOT NULL"
    params = []
    if project:
        q += " AND project=?"
        params.append(project)
    if date_str:
        from datetime import datetime
        start_ts = datetime.strptime(date_str, "%Y-%m-%d").timestamp()
        q += " AND start_ts >= ? AND start_ts < ?"
        params.extend([start_ts, start_ts + 86400])
    q += " GROUP BY project"
    rows = conn.execute(q, params).fetchall()
    return {r["project"]: r["total"] or 0 for r in rows}


def list_projects(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute("""SELECT project, COUNT(*) as sessions,
                           SUM(COALESCE(duration_s, 0)) as total
                           FROM time_entries GROUP BY project ORDER BY total DESC""").fetchall()
    return [{"project": r["project"], "sessions": r["sessions"], "total_seconds": r["total"] or 0}
            for r in rows]
