"""Context-aware classification — is this page productive given user's current goal?"""
from . import classifier, db

_cache = {}  # (title, goal) -> verdict


async def classify_context(api_key: str, domain: str, title: str, url_path: str,
                            user_context: str = "") -> str:
    """Returns: productive | distracting | neutral."""
    cache_key = (title, user_context)
    if cache_key in _cache:
        return _cache[cache_key]
    prompt = (
        f"User's current goal: {user_context or 'general productivity'}\n"
        f"They are viewing: {domain}{url_path}\n"
        f"Page title: {title}\n\n"
        f"Is this page 'productive' (supports the goal), 'distracting' (violates it), "
        f"or 'neutral' (unrelated)? Respond with ONLY one word."
    )
    try:
        result = await classifier.call_gemini(api_key, prompt, max_tokens=10)
        verdict = result.lower().strip()
        if verdict not in ("productive", "distracting", "neutral"):
            verdict = "neutral"
        _cache[cache_key] = verdict
        return verdict
    except Exception:
        return "neutral"


def set_current_context(conn, context: str):
    db.set_config(conn, "current_context", context)


def get_current_context(conn) -> str:
    return db.get_config(conn, "current_context", "") or ""


def clear_context(conn):
    db.set_config(conn, "current_context", "")
