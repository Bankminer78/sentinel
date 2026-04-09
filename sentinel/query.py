"""Natural language queries — chat with your accountability data."""
import json
from sentinel import db, classifier

ASK_PROMPT = """You are Sentinel, a productivity accountability assistant. Answer the user's question
using ONLY the data provided below. Be concise and specific. Use minutes/hours for durations.

User question: {question}

Recent rules:
{rules}

Recent activities (last 500, newest first):
{activities}

Config:
{config}

Answer in plain text, no markdown."""


def _summarize_activities(activities: list[dict], limit: int = 80) -> str:
    lines = []
    for a in activities[:limit]:
        lines.append(
            f"- {a.get('domain') or a.get('app') or '?'} "
            f"verdict={a.get('verdict') or 'allow'} "
            f"duration={round(a.get('duration_s') or 0, 1)}s")
    return "\n".join(lines) or "(no activities)"


def _summarize_rules(rules: list[dict]) -> str:
    return "\n".join(f"- #{r['id']}: {r['text']}" for r in rules) or "(no rules)"


def build_context(conn) -> dict:
    activities = db.get_activities(conn, limit=500)
    rules = db.get_rules(conn, active_only=False)
    cfg = {"api_key_set": bool(db.get_config(conn, "gemini_api_key"))}
    return {"activities": activities, "rules": rules, "config": cfg}


async def ask(conn, question: str, api_key: str) -> str:
    if not api_key:
        return "No API key configured. Run: sentinel config --api-key YOUR_KEY"
    if not question.strip():
        return "Please ask a question."
    ctx = build_context(conn)
    prompt = ASK_PROMPT.format(
        question=question.strip(),
        rules=_summarize_rules(ctx["rules"]),
        activities=_summarize_activities(ctx["activities"]),
        config=json.dumps(ctx["config"]))
    try:
        return await classifier.call_gemini(api_key, prompt, max_tokens=400)
    except Exception as e:
        return f"Error asking Gemini: {e}"
