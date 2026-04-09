"""Quantified self — aggregate all metrics into a unified daily score."""
from datetime import datetime
from . import db, stats as stats_mod


WEIGHTS = {
    "productivity": 0.30,
    "wellness": 0.20,
    "mood": 0.15,
    "habits": 0.15,
    "deep_work": 0.10,
    "meditation": 0.10,
}


def get_daily_score(conn, date_str: str = None) -> dict:
    """Aggregate score combining all metrics."""
    d = date_str or datetime.now().strftime("%Y-%m-%d")
    productivity = stats_mod.calculate_score(conn, d)
    wellness_score = _wellness_score(conn, d)
    mood_score = _mood_score(conn, d)
    habits_score = _habits_score(conn, d)
    deep_work_score = _deep_work_score(conn, d)
    meditation_score = _meditation_score(conn, d)
    components = {
        "productivity": productivity,
        "wellness": wellness_score,
        "mood": mood_score,
        "habits": habits_score,
        "deep_work": deep_work_score,
        "meditation": meditation_score,
    }
    total = sum(components[k] * WEIGHTS[k] for k in components)
    return {
        "date": d,
        "score": round(total, 1),
        "components": components,
        "weights": WEIGHTS,
    }


def _wellness_score(conn, date_str: str) -> float:
    try:
        from . import wellness
        totals = wellness.daily_totals(conn, date_str)
        score = 0
        if (totals.get("water_oz") or 0) >= 64:
            score += 30
        if (totals.get("eye_breaks") or 0) >= 5:
            score += 25
        if (totals.get("avg_posture") or 0) >= 7:
            score += 25
        if (totals.get("avg_energy") or 0) >= 6:
            score += 20
        return score
    except Exception:
        return 0


def _mood_score(conn, date_str: str) -> float:
    try:
        from . import mood
        # Use average mood for today scaled to 0-100
        avg = mood.average_mood(conn, days=1)
        return avg * 10
    except Exception:
        return 0


def _habits_score(conn, date_str: str) -> float:
    try:
        from . import habits
        today = habits.get_todays_habits(conn)
        if not today:
            return 0
        done = sum(1 for h in today if h.get("done"))
        return (done / len(today)) * 100
    except Exception:
        return 0


def _deep_work_score(conn, date_str: str) -> float:
    try:
        from . import deep_work
        hours = deep_work.total_hours(conn, days=1)
        return min(100, hours * 25)  # 4+ hours = 100
    except Exception:
        return 0


def _meditation_score(conn, date_str: str) -> float:
    try:
        from . import meditation
        minutes = meditation.total_minutes(conn, days=1)
        return min(100, minutes * 10)  # 10+ minutes = 100
    except Exception:
        return 0


def weekly_aggregate(conn) -> dict:
    """7-day rolling quantified self average."""
    from datetime import timedelta
    today = datetime.now().date()
    scores = []
    for i in range(7):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        result = get_daily_score(conn, d)
        scores.append(result["score"])
    avg = sum(scores) / len(scores) if scores else 0
    return {"avg": round(avg, 1), "days": scores}


def metric_trend(conn, metric: str, days: int = 14) -> str:
    """Is a specific component improving or declining?"""
    from datetime import timedelta
    today = datetime.now().date()
    first_half = []
    second_half = []
    for i in range(days):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        result = get_daily_score(conn, d)
        val = result["components"].get(metric, 0)
        if i < days // 2:
            second_half.append(val)
        else:
            first_half.append(val)
    if not first_half or not second_half:
        return "stable"
    avg1 = sum(first_half) / len(first_half)
    avg2 = sum(second_half) / len(second_half)
    if avg2 > avg1 + 5:
        return "improving"
    if avg2 < avg1 - 5:
        return "declining"
    return "stable"
