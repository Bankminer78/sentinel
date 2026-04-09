"""Recovery mode — help users get back on track after failures."""
import time
from . import classifier


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS recovery (
        id INTEGER PRIMARY KEY, start_ts REAL, end_ts REAL, reason TEXT, notes TEXT
    )""")
    conn.commit()


def enter_recovery_mode(conn, reason: str) -> int:
    _ensure_table(conn)
    active = conn.execute(
        "SELECT id FROM recovery WHERE end_ts IS NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if active:
        return active["id"]
    cur = conn.execute(
        "INSERT INTO recovery (start_ts, reason) VALUES (?, ?)",
        (time.time(), reason))
    conn.commit()
    return cur.lastrowid


def exit_recovery_mode(conn):
    _ensure_table(conn)
    conn.execute(
        "UPDATE recovery SET end_ts=? WHERE end_ts IS NULL",
        (time.time(),))
    conn.commit()


def is_in_recovery(conn) -> bool:
    _ensure_table(conn)
    r = conn.execute(
        "SELECT 1 FROM recovery WHERE end_ts IS NULL LIMIT 1"
    ).fetchone()
    return r is not None


def recovery_status(conn) -> dict:
    _ensure_table(conn)
    r = conn.execute(
        "SELECT * FROM recovery WHERE end_ts IS NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not r:
        return {"active": False}
    d = dict(r)
    return {
        "active": True,
        "id": d["id"],
        "reason": d["reason"],
        "start_ts": d["start_ts"],
        "duration_s": time.time() - d["start_ts"],
    }


_RECOVERY_PROMPT = """The user just experienced a failure of type '{failure_type}'.
Offer ONE short, compassionate, actionable recovery step (max 2 sentences)."""


async def suggest_recovery(conn, api_key: str, failure_type: str) -> str:
    prompt = _RECOVERY_PROMPT.format(failure_type=failure_type)
    try:
        return await classifier.call_gemini(api_key, prompt, max_tokens=120)
    except Exception:
        return "Take a breath. Reset one small habit today and move on."


def reset_streak_gracefully(conn, streak_name: str):
    _ensure_table(conn)
    r = conn.execute(
        "SELECT current, longest FROM streaks WHERE goal_name=?",
        (streak_name,)).fetchone()
    if not r:
        return
    longest = max(r["longest"] or 0, r["current"] or 0)
    conn.execute(
        "UPDATE streaks SET current=0, longest=? WHERE goal_name=?",
        (longest, streak_name))
    conn.commit()
