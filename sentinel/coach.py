"""Personal AI productivity coach — proactive insights and nudges."""
from . import classifier, db, stats

_BRIEF = """You are a productivity coach. Given yesterday's stats, give a concise morning briefing with 1-2 goals and a plan suggestion.

Yesterday: productive={p_hours}h distracted={d_hours}h score={score}
Respond in 3-4 sentences."""

_REFLECT = """You are a productivity coach giving end-of-day reflection. Note wins and lessons.

Today: productive={p_hours}h distracted={d_hours}h score={score}
Respond in 3-4 sentences."""

_MIDDAY = """You are a productivity coach doing a midday check-in.

So far today: productive={p_hours}h distracted={d_hours}h score={score}
Respond with a brief midday check-in (2-3 sentences)."""

_NUDGE = """You are a productivity coach. Give a context-aware motivational nudge.

Current activity: app={app} domain={domain} title={title}
Respond in 1-2 sentences."""

_PATTERN = """Analyze behavior patterns over {days} days. Stats: {summary}
Return a JSON object: {{"patterns": [...], "insights": [...], "recommendations": [...]}}
Return ONLY valid JSON."""

_WEEKLY = """Weekly review based on: {summary}
Return a JSON object: {{"wins": [...], "challenges": [...], "focus": "..."}}
Return ONLY valid JSON."""


def _day_stats(conn):
    h = stats.productive_vs_distracted_hours(conn)
    return h["productive_hours"], h["distracted_hours"], stats.calculate_score(conn)


async def morning_briefing(conn, api_key: str) -> str:
    p, d, s = _day_stats(conn)
    return await classifier.call_gemini(
        api_key, _BRIEF.format(p_hours=p, d_hours=d, score=s), max_tokens=200)


async def evening_reflection(conn, api_key: str) -> str:
    p, d, s = _day_stats(conn)
    return await classifier.call_gemini(
        api_key, _REFLECT.format(p_hours=p, d_hours=d, score=s), max_tokens=200)


async def mid_day_check_in(conn, api_key: str) -> str:
    p, d, s = _day_stats(conn)
    return await classifier.call_gemini(
        api_key, _MIDDAY.format(p_hours=p, d_hours=d, score=s), max_tokens=150)


async def pattern_analysis(conn, api_key: str, days: int = 14) -> dict:
    import json
    summary = stats._range_summary(conn, days)
    raw = await classifier.call_gemini(
        api_key, _PATTERN.format(days=days, summary=summary), max_tokens=400)
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"patterns": [], "insights": [], "recommendations": []}


async def personalized_nudge(conn, api_key: str, current_activity: dict) -> str:
    return await classifier.call_gemini(
        api_key, _NUDGE.format(
            app=current_activity.get("app", ""),
            domain=current_activity.get("domain", ""),
            title=current_activity.get("title", "")),
        max_tokens=100)


async def weekly_review(conn, api_key: str) -> dict:
    import json
    summary = stats.get_week_summary(conn)
    raw = await classifier.call_gemini(
        api_key, _WEEKLY.format(summary=summary), max_tokens=400)
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"wins": [], "challenges": [], "focus": ""}
