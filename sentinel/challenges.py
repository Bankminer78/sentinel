"""Time-limited challenges — e.g. 'No social media for 24 hours'."""
import time, json
from . import db


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS challenges (
        id INTEGER PRIMARY KEY, name TEXT, rules TEXT,
        start_ts REAL, end_ts REAL, status TEXT DEFAULT 'active'
    )""")


def create_challenge(conn, name: str, duration_hours: int, rules: list) -> int:
    _ensure_table(conn)
    now = time.time()
    cur = conn.execute(
        "INSERT INTO challenges (name, rules, start_ts, end_ts, status) VALUES (?, ?, ?, ?, 'active')",
        (name, json.dumps(rules), now, now + duration_hours * 3600))
    conn.commit()
    return cur.lastrowid


def get_challenge(conn, challenge_id: int) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM challenges WHERE id=?", (challenge_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["rules"] = json.loads(d["rules"]) if d["rules"] else []
    d["seconds_remaining"] = max(0, int(d["end_ts"] - time.time()))
    return d


def get_active_challenges(conn) -> list:
    _ensure_table(conn)
    now = time.time()
    rows = conn.execute(
        "SELECT * FROM challenges WHERE status='active' AND end_ts > ?", (now,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["rules"] = json.loads(d["rules"]) if d["rules"] else []
        d["seconds_remaining"] = max(0, int(d["end_ts"] - now))
        out.append(d)
    return out


def complete_challenge(conn, challenge_id: int) -> bool:
    _ensure_table(conn)
    c = get_challenge(conn, challenge_id)
    if not c:
        return False
    if c["seconds_remaining"] > 0:
        return False  # Can't complete until time is up
    conn.execute("UPDATE challenges SET status='completed' WHERE id=?", (challenge_id,))
    conn.commit()
    return True


def fail_challenge(conn, challenge_id: int):
    _ensure_table(conn)
    conn.execute("UPDATE challenges SET status='failed' WHERE id=?", (challenge_id,))
    conn.commit()


def challenge_stats(conn) -> dict:
    _ensure_table(conn)
    total = conn.execute("SELECT COUNT(*) as c FROM challenges").fetchone()["c"]
    completed = conn.execute("SELECT COUNT(*) as c FROM challenges WHERE status='completed'").fetchone()["c"]
    failed = conn.execute("SELECT COUNT(*) as c FROM challenges WHERE status='failed'").fetchone()["c"]
    active = len(get_active_challenges(conn))
    success_rate = (completed / (completed + failed) * 100) if (completed + failed) > 0 else 0
    return {"total": total, "completed": completed, "failed": failed,
            "active": active, "success_rate": round(success_rate, 1)}
