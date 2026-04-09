"""Natural language processing helpers for rules."""
import json
from sentinel import classifier

NORMALIZE_PROMPT = (
    "Clean up this rule so it is clear and concise. Keep the user's intent. "
    "Return only the cleaned text, no explanation.\n\nRule: {text}"
)

SPLIT_PROMPT = (
    "Split this compound rule into separate atomic rules, one per line. "
    "Return each resulting rule on its own line, no numbering, no explanation.\n\nRule: {text}"
)

INTENT_PROMPT = (
    "Extract the intent of this rule as JSON with fields: "
    '{{"action": "block"|"limit"|"allow", "targets": [strings], "time": "string", "duration": number}}. '
    "Use empty string or 0 when unknown. Return ONLY JSON.\n\nRule: {text}"
)

PHRASING_PROMPT = (
    "Suggest a clearer, more actionable phrasing of this rule. "
    "Return only the suggested text.\n\nRule: {text}"
)


async def normalize_rule_text(api_key: str, text: str) -> str:
    """Clean up user's natural language rule."""
    if not text.strip():
        return ""
    result = await classifier.call_gemini(api_key, NORMALIZE_PROMPT.format(text=text), max_tokens=150)
    return result.strip().strip('"').strip("'")


async def split_compound_rule(api_key: str, text: str) -> list[str]:
    """Split 'Block YouTube and Reddit' into two rules."""
    if not text.strip():
        return []
    result = await classifier.call_gemini(api_key, SPLIT_PROMPT.format(text=text), max_tokens=200)
    lines = [ln.strip("-*1234567890. \t") for ln in result.splitlines()]
    return [ln for ln in lines if ln]


async def extract_intent(api_key: str, text: str) -> dict:
    """Return {action, targets, time, duration}."""
    result = await classifier.call_gemini(api_key, INTENT_PROMPT.format(text=text), max_tokens=200)
    result = result.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        obj = json.loads(result)
    except json.JSONDecodeError:
        return {"action": "block", "targets": [], "time": "", "duration": 0}
    action = str(obj.get("action", "block")).lower()
    if action not in ("block", "limit", "allow"):
        action = "block"
    targets = obj.get("targets") or []
    if not isinstance(targets, list):
        targets = [str(targets)]
    try:
        duration = int(obj.get("duration", 0) or 0)
    except (ValueError, TypeError):
        duration = 0
    return {"action": action, "targets": [str(t) for t in targets],
            "time": str(obj.get("time", "") or ""), "duration": duration}


async def suggest_better_phrasing(api_key: str, text: str) -> str:
    """LLM suggests a clearer version of the user's rule."""
    if not text.strip():
        return ""
    result = await classifier.call_gemini(api_key, PHRASING_PROMPT.format(text=text), max_tokens=150)
    return result.strip().strip('"').strip("'")


def detect_conflicts(rule_a: dict, rule_b: dict) -> str | None:
    """Return conflict reason or None."""
    a_action = (rule_a.get("action") or "").lower()
    b_action = (rule_b.get("action") or "").lower()
    a_targets = set(rule_a.get("targets", []) or []) | set(rule_a.get("domains", []) or [])
    b_targets = set(rule_b.get("targets", []) or []) | set(rule_b.get("domains", []) or [])
    overlap = a_targets & b_targets
    if not overlap:
        a_cats = set(rule_a.get("categories", []) or [])
        b_cats = set(rule_b.get("categories", []) or [])
        overlap = a_cats & b_cats
    if not overlap:
        return None
    if a_action and b_action and a_action != b_action:
        if {a_action, b_action} & {"block", "allow"}:
            return f"conflicting actions {a_action} vs {b_action} on {sorted(overlap)}"
    return None
