"""Group challenges — challenges with multiple participants."""
import time, json


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS group_challenges (
        id INTEGER PRIMARY KEY, name TEXT, description TEXT,
        start_ts REAL, end_ts REAL, status TEXT DEFAULT 'active',
        created_by TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS group_challenge_members (
        challenge_id INTEGER, member TEXT, joined_at REAL, score REAL DEFAULT 0,
        PRIMARY KEY (challenge_id, member)
    )""")


def create_group_challenge(conn, name: str, description: str, duration_days: int,
                            created_by: str = "me") -> int:
    _ensure_tables(conn)
    now = time.time()
    cur = conn.execute(
        "INSERT INTO group_challenges (name, description, start_ts, end_ts, created_by) VALUES (?, ?, ?, ?, ?)",
        (name, description, now, now + duration_days * 86400, created_by))
    conn.commit()
    return cur.lastrowid


def join_challenge(conn, challenge_id: int, member: str):
    _ensure_tables(conn)
    conn.execute(
        "INSERT OR IGNORE INTO group_challenge_members (challenge_id, member, joined_at) VALUES (?, ?, ?)",
        (challenge_id, member, time.time()))
    conn.commit()


def leave_challenge(conn, challenge_id: int, member: str):
    _ensure_tables(conn)
    conn.execute(
        "DELETE FROM group_challenge_members WHERE challenge_id=? AND member=?",
        (challenge_id, member))
    conn.commit()


def update_member_score(conn, challenge_id: int, member: str, score: float):
    _ensure_tables(conn)
    conn.execute(
        "UPDATE group_challenge_members SET score=? WHERE challenge_id=? AND member=?",
        (score, challenge_id, member))
    conn.commit()


def get_challenge(conn, challenge_id: int) -> dict:
    _ensure_tables(conn)
    r = conn.execute("SELECT * FROM group_challenges WHERE id=?", (challenge_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["members"] = [dict(m) for m in conn.execute(
        "SELECT * FROM group_challenge_members WHERE challenge_id=? ORDER BY score DESC",
        (challenge_id,)).fetchall()]
    d["seconds_remaining"] = max(0, int(d["end_ts"] - time.time()))
    return d


def list_challenges(conn, status: str = "active") -> list:
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT * FROM group_challenges WHERE status=?", (status,)).fetchall()
    return [dict(r) for r in rows]


def get_leaderboard(conn, challenge_id: int) -> list:
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT * FROM group_challenge_members WHERE challenge_id=? ORDER BY score DESC",
        (challenge_id,)).fetchall()
    return [dict(r) for r in rows]


def finalize(conn, challenge_id: int) -> dict:
    _ensure_tables(conn)
    challenge = get_challenge(conn, challenge_id)
    if not challenge:
        return None
    conn.execute("UPDATE group_challenges SET status='completed' WHERE id=?", (challenge_id,))
    conn.commit()
    # Winner is the one with highest score
    members = challenge.get("members", [])
    winner = members[0] if members else None
    return {"challenge": challenge, "winner": winner}


def delete_challenge(conn, challenge_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM group_challenges WHERE id=?", (challenge_id,))
    conn.execute("DELETE FROM group_challenge_members WHERE challenge_id=?", (challenge_id,))
    conn.commit()
