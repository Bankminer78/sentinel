"""Digital detox programs — structured detox challenges."""
import time


DETOX_PROGRAMS = {
    "24_hour": {
        "name": "24-Hour Digital Fast",
        "duration_hours": 24,
        "description": "Zero devices for 24 hours",
        "rules": ["block_all_internet", "block_all_apps"],
    },
    "weekend": {
        "name": "Weekend Off",
        "duration_hours": 48,
        "description": "Full weekend off screens",
        "rules": ["block_social", "block_streaming", "block_gaming"],
    },
    "work_week_focus": {
        "name": "Work Week Focus",
        "duration_hours": 120,
        "description": "No distractions Mon-Fri",
        "rules": ["block_social", "block_streaming"],
    },
    "social_fast": {
        "name": "Social Media Fast",
        "duration_hours": 168,
        "description": "Week without social media",
        "rules": ["block_social"],
    },
    "news_fast": {
        "name": "News Fast",
        "duration_hours": 168,
        "description": "Week without news",
        "rules": ["block_news"],
    },
    "entertainment_fast": {
        "name": "Entertainment Fast",
        "duration_hours": 168,
        "description": "No Netflix, YouTube, gaming for a week",
        "rules": ["block_streaming", "block_gaming"],
    },
    "morning_only": {
        "name": "Morning Only",
        "duration_hours": 24,
        "description": "Devices only allowed before noon",
        "rules": ["schedule_after_noon"],
    },
    "minimum_phone": {
        "name": "Minimum Phone",
        "duration_hours": 168,
        "description": "Phone only for calls and navigation",
        "rules": ["block_all_apps_except_essential"],
    },
}


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS detox_sessions (
        id INTEGER PRIMARY KEY, program_id TEXT, start_ts REAL, end_ts REAL,
        completed INTEGER, notes TEXT
    )""")


def list_programs() -> list:
    return [{"id": k, **v} for k, v in DETOX_PROGRAMS.items()]


def get_program(program_id: str) -> dict:
    return DETOX_PROGRAMS.get(program_id)


def start_detox(conn, program_id: str) -> int:
    _ensure_table(conn)
    program = get_program(program_id)
    if not program:
        return 0
    now = time.time()
    cur = conn.execute(
        "INSERT INTO detox_sessions (program_id, start_ts, end_ts, completed) VALUES (?, ?, ?, 0)",
        (program_id, now, now + program["duration_hours"] * 3600))
    conn.commit()
    return cur.lastrowid


def get_active_detox(conn) -> dict:
    _ensure_table(conn)
    now = time.time()
    r = conn.execute(
        "SELECT * FROM detox_sessions WHERE completed=0 AND end_ts > ? LIMIT 1", (now,)
    ).fetchone()
    if not r:
        return None
    d = dict(r)
    d["remaining_seconds"] = max(0, int(d["end_ts"] - now))
    program = get_program(d["program_id"])
    if program:
        d["program"] = program
    return d


def complete_detox(conn, session_id: int, notes: str = ""):
    _ensure_table(conn)
    conn.execute(
        "UPDATE detox_sessions SET completed=1, notes=? WHERE id=?",
        (notes, session_id))
    conn.commit()


def fail_detox(conn, session_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM detox_sessions WHERE id=?", (session_id,))
    conn.commit()


def get_detox_history(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM detox_sessions ORDER BY start_ts DESC").fetchall()
    return [dict(r) for r in rows]


def completed_detoxes(conn) -> int:
    _ensure_table(conn)
    r = conn.execute(
        "SELECT COUNT(*) as c FROM detox_sessions WHERE completed=1").fetchone()
    return r["c"] if r else 0


def total_programs() -> int:
    return len(DETOX_PROGRAMS)


def success_rate(conn) -> float:
    _ensure_table(conn)
    total = conn.execute("SELECT COUNT(*) as c FROM detox_sessions").fetchone()["c"]
    if total == 0:
        return 0
    completed = completed_detoxes(conn)
    return round(completed / total * 100, 1)
