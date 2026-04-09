"""Reports and insights — human-readable summaries."""
import json
from datetime import datetime
from collections import Counter
from . import db, stats as stats_mod, classifier


async def daily_report(conn, api_key: str, date_str: str = None) -> str:
    """Natural language daily summary via Gemini."""
    breakdown = stats_mod.get_daily_breakdown(conn, date_str)
    score = stats_mod.calculate_score(conn, date_str)
    top = stats_mod.get_top_distractions(conn, days=1, limit=5)
    prompt = (
        f"Give a brief (2-3 sentence) productivity summary for the user. Be friendly but honest.\n"
        f"Score: {score}/100\n"
        f"Breakdown: {json.dumps(breakdown)}\n"
        f"Top distractions: {top[:3]}"
    )
    try:
        return await classifier.call_gemini(api_key, prompt, max_tokens=200)
    except Exception:
        return f"Today's score: {score}/100. See `sentinel stats` for details."


async def weekly_insights(conn, api_key: str) -> dict:
    """Returns: {summary, patterns, recommendations}."""
    week = stats_mod.get_week_summary(conn)
    top = stats_mod.get_top_distractions(conn, days=7, limit=10)
    prompt = (
        f"Analyze this user's week and give JSON: {{\"summary\": str, \"patterns\": [str], \"recommendations\": [str]}}\n"
        f"Week: {json.dumps(week)}\n"
        f"Top distractions: {top[:5]}\n"
        f"Be specific and actionable. 2-3 items per list."
    )
    try:
        result = await classifier.call_gemini(api_key, prompt, max_tokens=400)
        result = result.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(result)
    except Exception:
        return {"summary": "Week summary unavailable", "patterns": [], "recommendations": []}


def time_distribution(conn, date_str: str = None) -> dict:
    """Hourly breakdown of activity."""
    activities = db.get_activities(conn, limit=10000)
    hours = Counter()
    for a in activities:
        if a.get("ts"):
            if date_str:
                if datetime.fromtimestamp(a["ts"]).strftime("%Y-%m-%d") != date_str:
                    continue
            hour = datetime.fromtimestamp(a["ts"]).hour
            hours[hour] += a.get("duration_s") or 0
    return {str(h): hours.get(h, 0) for h in range(24)}


def peak_focus_hours(conn, days: int = 30) -> list:
    """Hours (0-23) when user is most productive."""
    import time
    cutoff = time.time() - (days * 86400)
    activities = db.get_activities(conn, since=cutoff, limit=10000)
    hour_productive = Counter()
    for a in activities:
        if a.get("verdict") == "allow" and a.get("domain"):
            seen = db.get_seen(conn, a["domain"])
            if seen == "none" or seen is None:
                hour = datetime.fromtimestamp(a["ts"]).hour
                hour_productive[hour] += 1
    return [h for h, _ in hour_productive.most_common(5)]


def distraction_triggers(conn) -> list:
    """What typically precedes distraction?"""
    activities = sorted(db.get_activities(conn, limit=500), key=lambda a: a.get("ts", 0))
    triggers = []
    for i, a in enumerate(activities[1:], 1):
        dom = a.get("domain")
        if not dom:
            continue
        seen = db.get_seen(conn, dom)
        if seen in ("social", "streaming"):
            prev = activities[i - 1]
            prev_dom = prev.get("domain") or prev.get("app") or "idle"
            triggers.append({"trigger": prev_dom, "then": dom})
    # Count most common triggers
    c = Counter((t["trigger"], t["then"]) for t in triggers)
    return [{"trigger": k[0], "distraction": k[1], "count": v}
            for k, v in c.most_common(10)]
