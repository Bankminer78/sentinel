"""XP / leveling system — reward points for productive actions."""
import math
import time

_REWARDS = {
    "completed_pomodoro": 25,
    "focus_session": 50,
    "goal_met": 30,
    "rule_created": 10,
    "achievement": 100,
    "achievement_unlocked": 100,
    "day_streak": 15,
    "intervention_passed": 5,
    "challenge_completed": 200,
}


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS points_log (
        id INTEGER PRIMARY KEY, amount INTEGER, reason TEXT, ts REAL
    )""")


def add_points(conn, amount: int, reason: str = "") -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO points_log (amount, reason, ts) VALUES (?,?,?)",
        (int(amount), reason, time.time()))
    conn.commit()
    return cur.lastrowid


def get_total_points(conn) -> int:
    _ensure_table(conn)
    r = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS t FROM points_log").fetchone()
    return int(r["t"] or 0)


def level_for_points(points: int) -> int:
    if points <= 0:
        return 1
    return int(math.floor(math.sqrt(points / 100))) + 1


def points_for_level(level: int) -> int:
    return ((level - 1) ** 2) * 100


_points_for_level = points_for_level


def get_level(conn) -> dict:
    total = get_total_points(conn)
    lvl = level_for_points(total)
    cur_base = _points_for_level(lvl)
    next_base = _points_for_level(lvl + 1)
    span = next_base - cur_base
    cur_xp = total - cur_base
    progress = round(100.0 * cur_xp / span, 2) if span else 0.0
    return {
        "level": lvl,
        "current_xp": cur_xp,
        "next_level_xp": span,
        "progress_percent": progress,
        "total_points": total,
    }


def points_for_action(action: str) -> int:
    return int(_REWARDS.get(action, 0))


def award(conn, action: str) -> int:
    amt = points_for_action(action)
    if amt:
        add_points(conn, amt, reason=action)
    return get_total_points(conn)


def get_log(conn, limit: int = 50) -> list[dict]:
    _ensure_table(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM points_log ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()]


get_history = get_log
