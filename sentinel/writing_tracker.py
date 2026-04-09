"""Writing tracker — words written, projects, streaks."""
import time
from datetime import datetime, timedelta


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS writing_projects (
        id INTEGER PRIMARY KEY, name TEXT, word_goal INTEGER DEFAULT 0,
        current_words INTEGER DEFAULT 0, status TEXT DEFAULT 'active', created_at REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS writing_sessions (
        id INTEGER PRIMARY KEY, project_id INTEGER, words INTEGER,
        minutes INTEGER, note TEXT, ts REAL
    )""")


def create_project(conn, name: str, word_goal: int = 0) -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO writing_projects (name, word_goal, created_at) VALUES (?, ?, ?)",
        (name, word_goal, time.time()))
    conn.commit()
    return cur.lastrowid


def get_projects(conn, status: str = "active") -> list:
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT * FROM writing_projects WHERE status=?", (status,)).fetchall()
    return [dict(r) for r in rows]


def log_writing(conn, project_id: int, words: int, minutes: int = 0, note: str = "") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO writing_sessions (project_id, words, minutes, note, ts) VALUES (?, ?, ?, ?, ?)",
        (project_id, words, minutes, note, time.time()))
    conn.execute(
        "UPDATE writing_projects SET current_words = current_words + ? WHERE id=?",
        (words, project_id))
    conn.commit()
    return cur.lastrowid


def complete_project(conn, project_id: int):
    _ensure_tables(conn)
    conn.execute("UPDATE writing_projects SET status='complete' WHERE id=?", (project_id,))
    conn.commit()


def words_today(conn) -> int:
    _ensure_tables(conn)
    start = datetime.combine(datetime.now().date(), datetime.min.time()).timestamp()
    r = conn.execute(
        "SELECT COALESCE(SUM(words), 0) as total FROM writing_sessions WHERE ts >= ?",
        (start,)).fetchone()
    return r["total"] or 0


def words_this_week(conn) -> int:
    _ensure_tables(conn)
    monday = datetime.now().date() - timedelta(days=datetime.now().weekday())
    start = datetime.combine(monday, datetime.min.time()).timestamp()
    r = conn.execute(
        "SELECT COALESCE(SUM(words), 0) as total FROM writing_sessions WHERE ts >= ?",
        (start,)).fetchone()
    return r["total"] or 0


def writing_streak(conn) -> int:
    _ensure_tables(conn)
    current = datetime.now().date()
    days = 0
    while True:
        day_start = datetime.combine(current, datetime.min.time()).timestamp()
        day_end = day_start + 86400
        r = conn.execute(
            "SELECT COUNT(*) as c FROM writing_sessions WHERE ts >= ? AND ts < ?",
            (day_start, day_end)).fetchone()
        if r["c"] > 0:
            days += 1
            current -= timedelta(days=1)
        else:
            if days == 0 and current == datetime.now().date():
                current -= timedelta(days=1)
                continue
            break
    return days


def project_progress(conn, project_id: int) -> dict:
    _ensure_tables(conn)
    r = conn.execute("SELECT * FROM writing_projects WHERE id=?", (project_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    if d["word_goal"] > 0:
        d["percent"] = min(100, round(d["current_words"] / d["word_goal"] * 100, 1))
    else:
        d["percent"] = 0
    return d


def recent_sessions(conn, limit: int = 20) -> list:
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT * FROM writing_sessions ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def avg_words_per_day(conn, days: int = 30) -> float:
    _ensure_tables(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute(
        "SELECT COALESCE(SUM(words), 0) as total FROM writing_sessions WHERE ts >= ?",
        (cutoff,)).fetchone()
    return round((r["total"] or 0) / days, 1)
