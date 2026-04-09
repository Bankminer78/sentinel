"""Daily/weekly digest — summary of productivity."""
import json
from . import db, stats as stats_mod, classifier, notifications


def _stats_for_day(conn) -> dict:
    return {
        "score": stats_mod.calculate_score(conn),
        "breakdown": stats_mod.get_daily_breakdown(conn),
        "top_distractions": stats_mod.get_top_distractions(conn, days=1, limit=5),
    }


def _stats_for_week(conn) -> dict:
    return {
        "week": stats_mod.get_week_summary(conn),
        "top_distractions": stats_mod.get_top_distractions(conn, days=7, limit=5),
    }


async def generate_daily_digest(conn, api_key: str) -> str:
    """Generate a nicely formatted daily digest via LLM, with fallback."""
    s = _stats_for_day(conn)
    prompt = (
        "Write a short (3-4 sentence) daily productivity digest for the user. "
        "Friendly, honest, actionable.\n"
        f"Score: {s['score']}/100\n"
        f"Breakdown: {json.dumps(s['breakdown'])}\n"
        f"Top distractions: {s['top_distractions']}"
    )
    try:
        return await classifier.call_gemini(api_key, prompt, max_tokens=200)
    except Exception:
        return f"Daily digest — score {s['score']}/100."


async def generate_weekly_digest(conn, api_key: str) -> str:
    s = _stats_for_week(conn)
    prompt = (
        "Write a short (4-5 sentence) weekly productivity digest. "
        "Highlight trends, wins, and one improvement.\n"
        f"Week: {json.dumps(s['week'])}\n"
        f"Top distractions: {s['top_distractions']}"
    )
    try:
        return await classifier.call_gemini(api_key, prompt, max_tokens=300)
    except Exception:
        return f"Weekly digest — avg score {s['week'].get('avg_score', 0)}/100."


def format_digest_html(digest_text: str, stats: dict) -> str:
    score = stats.get("score", stats.get("week", {}).get("avg_score", 0))
    return (
        "<!DOCTYPE html><html><body style='font-family:sans-serif;background:#18181b;color:#e4e4e7;padding:20px'>"
        "<h1 style='color:#ef4444'>Sentinel Digest</h1>"
        f"<p>{digest_text}</p>"
        f"<p><strong>Score:</strong> {score}/100</p>"
        f"<pre style='background:#27272a;padding:10px'>{json.dumps(stats, indent=2)}</pre>"
        "</body></html>"
    )


def format_digest_markdown(digest_text: str, stats: dict) -> str:
    score = stats.get("score", stats.get("week", {}).get("avg_score", 0))
    lines = [
        "# Sentinel Digest",
        "",
        digest_text,
        "",
        f"**Score:** {score}/100",
        "",
        "```json",
        json.dumps(stats, indent=2),
        "```",
    ]
    return "\n".join(lines)


async def send_digest(conn, api_key: str, channels: list = None) -> dict:
    """Generate and send digest via the given notification channels."""
    text = await generate_daily_digest(conn, api_key)
    stats = _stats_for_day(conn)
    body = format_digest_markdown(text, stats)
    return await notifications.send_all(conn, "Sentinel Daily Digest", body, channels=channels)
