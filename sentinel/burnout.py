"""Burnout detection — spot warning signs."""
import time
from datetime import datetime, timedelta
from collections import Counter
from . import db, classifier

INDICATORS = {
    "long_hours": "Working > 10h/day consistently",
    "no_breaks": "No breaks taken",
    "late_nights": "Working past 11pm regularly",
    "weekend_work": "Working on weekends",
    "declining_score": "Productivity score trending down",
    "high_distraction": "Distraction time increasing",
}


def _get_recent_activities(conn, days: int = 7) -> list:
    cutoff = time.time() - days * 86400
    return db.get_activities(conn, since=cutoff, limit=10000)


def check_long_hours(conn) -> bool:
    activities = _get_recent_activities(conn, days=7)
    by_day = Counter()
    for a in activities:
        if a.get("ts"):
            day = datetime.fromtimestamp(a["ts"]).strftime("%Y-%m-%d")
            by_day[day] += a.get("duration_s") or 0
    long_days = sum(1 for s in by_day.values() if s > 10 * 3600)
    return long_days >= 3


def check_no_breaks(conn) -> bool:
    # Check for pomodoro/focus session breaks in last 7 days
    r = conn.execute(
        "SELECT COUNT(*) as c FROM pomodoro_sessions WHERE start_ts > ?",
        (time.time() - 7 * 86400,)).fetchone() if _table_exists(conn, "pomodoro_sessions") else None
    return (r is None or r["c"] == 0)


def check_late_nights(conn) -> bool:
    activities = _get_recent_activities(conn, days=7)
    late = sum(1 for a in activities
               if a.get("ts") and datetime.fromtimestamp(a["ts"]).hour >= 23)
    return late > 5


def check_weekend_work(conn) -> bool:
    activities = _get_recent_activities(conn, days=14)
    weekend = sum(1 for a in activities
                  if a.get("ts") and datetime.fromtimestamp(a["ts"]).weekday() >= 5)
    return weekend > 10


def check_declining_score(conn) -> bool:
    from . import stats as stats_mod
    try:
        week = stats_mod.get_week_summary(conn)
        days = week.get("days", [])
        if not isinstance(days, list) or len(days) < 4:
            return False
        scores = [d.get("score", 0) if isinstance(d, dict) else 0 for d in days]
        first_half = scores[:len(scores) // 2]
        second_half = scores[len(scores) // 2:]
        if not first_half or not second_half:
            return False
        return (sum(second_half) / len(second_half)) < (sum(first_half) / len(first_half)) - 10
    except Exception:
        return False


def check_high_distraction(conn) -> bool:
    activities = _get_recent_activities(conn, days=7)
    distracting = sum(1 for a in activities if a.get("verdict") == "block")
    return distracting > 20


def _table_exists(conn, name: str) -> bool:
    r = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return r is not None


def calculate_burnout_score(conn) -> dict:
    """Score 0-100, higher = more burnout risk."""
    checks = {
        "long_hours": check_long_hours(conn),
        "no_breaks": check_no_breaks(conn),
        "late_nights": check_late_nights(conn),
        "weekend_work": check_weekend_work(conn),
        "declining_score": check_declining_score(conn),
        "high_distraction": check_high_distraction(conn),
    }
    triggered = [k for k, v in checks.items() if v]
    score = len(triggered) * (100 // len(checks))
    severity = "low" if score < 33 else "medium" if score < 67 else "high"
    return {"score": score, "indicators": triggered, "severity": severity}


async def burnout_alert(conn, api_key: str) -> dict:
    result = calculate_burnout_score(conn)
    if result["score"] < 50:
        return result
    prompt = (f"The user's burnout score is {result['score']}/100 with indicators: "
              f"{result['indicators']}. Give a gentle 2-sentence warning.")
    try:
        result["message"] = await classifier.call_gemini(api_key, prompt, max_tokens=150)
    except Exception:
        result["message"] = "High burnout risk detected. Consider taking a real break."
    return result


def recommend_rest(conn) -> list:
    checks = calculate_burnout_score(conn)
    recs = []
    if "long_hours" in checks["indicators"]:
        recs.append("Cap your workday at 8 hours")
    if "no_breaks" in checks["indicators"]:
        recs.append("Take a 10-min break every 90 minutes")
    if "late_nights" in checks["indicators"]:
        recs.append("Stop working by 10pm")
    if "weekend_work" in checks["indicators"]:
        recs.append("Block all work domains on weekends")
    if "declining_score" in checks["indicators"]:
        recs.append("Reassess your priorities — not everything is important")
    return recs
