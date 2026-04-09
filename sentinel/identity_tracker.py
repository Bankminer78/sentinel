"""Identity-based habits — track identity affirmations (James Clear style)."""
import time
from datetime import datetime, timedelta


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS identities (
        id INTEGER PRIMARY KEY, identity TEXT UNIQUE,
        description TEXT, created_at REAL, active INTEGER DEFAULT 1
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS identity_votes (
        id INTEGER PRIMARY KEY, identity_id INTEGER, action TEXT,
        date TEXT, ts REAL
    )""")


def add_identity(conn, identity: str, description: str = "") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT OR IGNORE INTO identities (identity, description, created_at) VALUES (?, ?, ?)",
        (identity, description, time.time()))
    if cur.lastrowid == 0:
        r = conn.execute("SELECT id FROM identities WHERE identity=?", (identity,)).fetchone()
        conn.commit()
        return r["id"] if r else 0
    conn.commit()
    return cur.lastrowid


def get_identities(conn, active_only: bool = True) -> list:
    _ensure_tables(conn)
    q = "SELECT * FROM identities"
    if active_only:
        q += " WHERE active=1"
    return [dict(r) for r in conn.execute(q).fetchall()]


def cast_vote(conn, identity_id: int, action: str) -> int:
    """Cast a vote for (or against) your identity."""
    _ensure_tables(conn)
    date_str = datetime.now().strftime("%Y-%m-%d")
    cur = conn.execute(
        "INSERT INTO identity_votes (identity_id, action, date, ts) VALUES (?, ?, ?, ?)",
        (identity_id, action, date_str, time.time()))
    conn.commit()
    return cur.lastrowid


def votes_count(conn, identity_id: int, days: int = 30) -> int:
    _ensure_tables(conn)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    r = conn.execute(
        "SELECT COUNT(*) as c FROM identity_votes WHERE identity_id=? AND date >= ?",
        (identity_id, cutoff)).fetchone()
    return r["c"] if r else 0


def deactivate(conn, identity_id: int):
    _ensure_tables(conn)
    conn.execute("UPDATE identities SET active=0 WHERE id=?", (identity_id,))
    conn.commit()


def delete_identity(conn, identity_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM identities WHERE id=?", (identity_id,))
    conn.execute("DELETE FROM identity_votes WHERE identity_id=?", (identity_id,))
    conn.commit()


def get_recent_votes(conn, identity_id: int, limit: int = 30) -> list:
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT * FROM identity_votes WHERE identity_id=? ORDER BY ts DESC LIMIT ?",
        (identity_id, limit)).fetchall()
    return [dict(r) for r in rows]


def votes_today(conn, identity_id: int) -> int:
    _ensure_tables(conn)
    today = datetime.now().strftime("%Y-%m-%d")
    r = conn.execute(
        "SELECT COUNT(*) as c FROM identity_votes WHERE identity_id=? AND date=?",
        (identity_id, today)).fetchone()
    return r["c"] if r else 0


def identity_progress(conn, identity_id: int) -> dict:
    _ensure_tables(conn)
    r = conn.execute("SELECT * FROM identities WHERE id=?", (identity_id,)).fetchone()
    if not r:
        return None
    return {
        **dict(r),
        "total_votes": votes_count(conn, identity_id, days=365),
        "last_30_days": votes_count(conn, identity_id, days=30),
        "today": votes_today(conn, identity_id),
    }


def all_identities_progress(conn) -> list:
    identities = get_identities(conn)
    return [identity_progress(conn, i["id"]) for i in identities]


def streak(conn, identity_id: int) -> int:
    """Consecutive days with at least one vote."""
    _ensure_tables(conn)
    current = datetime.now().date()
    days = 0
    while True:
        dstr = current.strftime("%Y-%m-%d")
        r = conn.execute(
            "SELECT COUNT(*) as c FROM identity_votes WHERE identity_id=? AND date=?",
            (identity_id, dstr)).fetchone()
        if r["c"] > 0:
            days += 1
            current -= timedelta(days=1)
        else:
            if days == 0 and current == datetime.now().date():
                current -= timedelta(days=1)
                continue
            break
    return days
