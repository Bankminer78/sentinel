"""Public commitments — share commitments for social accountability."""
import time


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS public_commitments (
        id INTEGER PRIMARY KEY, text TEXT, deadline TEXT, platform TEXT,
        stakes TEXT, url TEXT, status TEXT DEFAULT 'pending',
        shared_at REAL, completed_at REAL
    )""")


def add_commitment(conn, text: str, deadline: str, platform: str = "twitter",
                   stakes: str = "", url: str = "") -> int:
    _ensure_table(conn)
    cur = conn.execute(
        """INSERT INTO public_commitments (text, deadline, platform, stakes, url, shared_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (text, deadline, platform, stakes, url, time.time()))
    conn.commit()
    return cur.lastrowid


def get_commitments(conn, status: str = None) -> list:
    _ensure_table(conn)
    q = "SELECT * FROM public_commitments"
    params = []
    if status:
        q += " WHERE status=?"
        params.append(status)
    q += " ORDER BY shared_at DESC"
    rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def mark_completed(conn, commitment_id: int):
    _ensure_table(conn)
    conn.execute(
        "UPDATE public_commitments SET status='completed', completed_at=? WHERE id=?",
        (time.time(), commitment_id))
    conn.commit()


def mark_failed(conn, commitment_id: int):
    _ensure_table(conn)
    conn.execute(
        "UPDATE public_commitments SET status='failed' WHERE id=?", (commitment_id,))
    conn.commit()


def delete_commitment(conn, commitment_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM public_commitments WHERE id=?", (commitment_id,))
    conn.commit()


def overdue(conn) -> list:
    _ensure_table(conn)
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM public_commitments WHERE status='pending' AND deadline < ?",
        (today,)).fetchall()
    return [dict(r) for r in rows]


def pending_commitments(conn) -> list:
    return get_commitments(conn, "pending")


def completed_commitments(conn) -> list:
    return get_commitments(conn, "completed")


def failed_commitments(conn) -> list:
    return get_commitments(conn, "failed")


def commitment_rate(conn) -> float:
    _ensure_table(conn)
    total = conn.execute("SELECT COUNT(*) as c FROM public_commitments").fetchone()["c"]
    if total == 0:
        return 0
    completed = conn.execute(
        "SELECT COUNT(*) as c FROM public_commitments WHERE status='completed'").fetchone()["c"]
    return round(completed / total * 100, 1)


def format_for_twitter(commitment: dict) -> str:
    """Format commitment text for Twitter."""
    text = f"I commit to: {commitment['text']}"
    if commitment.get("deadline"):
        text += f" by {commitment['deadline']}"
    if commitment.get("stakes"):
        text += f". Stakes: {commitment['stakes']}"
    text += " #accountability"
    return text[:280]


def format_for_linkedin(commitment: dict) -> str:
    text = f"I'm publicly committing to: {commitment['text']}"
    if commitment.get("deadline"):
        text += f"\n\nDeadline: {commitment['deadline']}"
    if commitment.get("stakes"):
        text += f"\nStakes: {commitment['stakes']}"
    return text


def total_count(conn) -> int:
    _ensure_table(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM public_commitments").fetchone()
    return r["c"] if r else 0
