"""Achievement system — unlock badges for productivity milestones."""
import time
from . import db

ACHIEVEMENTS = {
    "first_day": {"name": "First Day", "desc": "Use Sentinel for 1 day"},
    "week_streak": {"name": "Week Warrior", "desc": "7-day productivity streak"},
    "month_streak": {"name": "Month Master", "desc": "30-day productivity streak"},
    "no_social_day": {"name": "Social Detox", "desc": "Zero social media in a day"},
    "focus_hour": {"name": "Focus Hour", "desc": "Complete a 60min focus session"},
    "pomodoro_pro": {"name": "Pomodoro Pro", "desc": "Complete 10 pomodoros"},
    "rule_maker": {"name": "Rule Maker", "desc": "Create 10 rules"},
    "blocker": {"name": "Blocker", "desc": "Block 100 distractions"},
    "comeback": {"name": "Comeback Kid", "desc": "Hit 80+ score after a bad day"},
    "top_score": {"name": "Perfectionist", "desc": "Hit 95+ productivity score"},
    "rule_collector": {"name": "Rule Collector", "desc": "Create 25 rules"},
    "focused_week": {"name": "Focused Week", "desc": "7 days with 70+ score"},
    "no_distraction_hour": {"name": "Deep Work", "desc": "1 hour of pure productive time"},
    "early_bird": {"name": "Early Bird", "desc": "Productive before 8am"},
    "night_owl": {"name": "Night Owl", "desc": "Productive after 10pm"},
}


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS achievements (
        id TEXT PRIMARY KEY, unlocked_at REAL
    )""")


def unlock(conn, achievement_id: str) -> bool:
    """Unlock an achievement if not already unlocked. Returns True if newly unlocked."""
    _ensure_table(conn)
    if achievement_id not in ACHIEVEMENTS:
        return False
    if is_unlocked(conn, achievement_id):
        return False
    conn.execute("INSERT INTO achievements (id, unlocked_at) VALUES (?, ?)",
                 (achievement_id, time.time()))
    conn.commit()
    return True


def is_unlocked(conn, achievement_id: str) -> bool:
    _ensure_table(conn)
    return conn.execute("SELECT 1 FROM achievements WHERE id=?", (achievement_id,)).fetchone() is not None


def get_unlocked(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute("SELECT id, unlocked_at FROM achievements ORDER BY unlocked_at DESC").fetchall()
    return [{**ACHIEVEMENTS[r["id"]], "id": r["id"], "unlocked_at": r["unlocked_at"]}
            for r in rows if r["id"] in ACHIEVEMENTS]


def get_locked(conn) -> list:
    _ensure_table(conn)
    unlocked_ids = {r["id"] for r in conn.execute("SELECT id FROM achievements").fetchall()}
    return [{**v, "id": k} for k, v in ACHIEVEMENTS.items() if k not in unlocked_ids]


def get_all_achievements() -> list:
    return [{**v, "id": k} for k, v in ACHIEVEMENTS.items()]


def check_achievements(conn) -> list:
    """Evaluate all achievements, unlock newly earned ones. Returns newly unlocked list."""
    newly = []
    # Count rules
    n_rules = len(db.get_rules(conn, active_only=False))
    if n_rules >= 10 and unlock(conn, "rule_maker"):
        newly.append("rule_maker")
    if n_rules >= 25 and unlock(conn, "rule_collector"):
        newly.append("rule_collector")
    # Count blocks
    activities = db.get_activities(conn, limit=10000)
    n_blocks = sum(1 for a in activities if a.get("verdict") == "block")
    if n_blocks >= 100 and unlock(conn, "blocker"):
        newly.append("blocker")
    # First day
    if n_rules > 0 or activities:
        if unlock(conn, "first_day"):
            newly.append("first_day")
    return newly
