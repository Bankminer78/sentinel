"""Smart rule analysis — conflicts, duplicates, LLM-suggested rules."""
from collections import Counter
from . import db, classifier


def find_duplicates(conn) -> list:
    """Find rules with identical text (case-insensitive)."""
    rules = db.get_rules(conn, active_only=False)
    seen = {}
    dupes = []
    for r in rules:
        key = r["text"].lower().strip()
        if key in seen:
            dupes.append({"original": seen[key], "duplicate": r})
        else:
            seen[key] = r
    return dupes


def find_conflicts(conn) -> list:
    """Find rules that might conflict (same domain referenced differently)."""
    rules = db.get_rules(conn, active_only=False)
    domain_rules = {}  # domain -> [rule ids]
    import json
    for r in rules:
        try:
            parsed = json.loads(r.get("parsed", "{}")) if isinstance(r.get("parsed"), str) else r.get("parsed", {})
            for d in parsed.get("domains", []):
                domain_rules.setdefault(d, []).append(r)
        except Exception:
            continue
    return [{"domain": d, "rules": rs} for d, rs in domain_rules.items() if len(rs) > 1]


async def suggest_rules(conn, api_key: str) -> list:
    """LLM analyzes activity, suggests rules."""
    # Get top distracting domains not yet covered by rules
    activities = db.get_activities(conn, limit=500)
    distracting_domains = Counter()
    for a in activities:
        dom = a.get("domain")
        if dom:
            seen = db.get_seen(conn, dom)
            if seen in ("streaming", "social", "adult", "gaming"):
                distracting_domains[dom] += 1
    if not distracting_domains:
        return []
    top = distracting_domains.most_common(5)
    suggestions = []
    for dom, count in top:
        suggestions.append(f"Block {dom} — you visited it {count} times recently")
    return suggestions


def coverage_report(conn) -> dict:
    """How well are your distractions covered by rules?"""
    activities = db.get_activities(conn, limit=1000)
    total_distracting = 0
    blocked = 0
    for a in activities:
        dom = a.get("domain")
        if not dom:
            continue
        seen = db.get_seen(conn, dom)
        if seen in ("streaming", "social", "adult", "gaming"):
            total_distracting += 1
            if a.get("verdict") == "block":
                blocked += 1
    rate = (blocked / total_distracting * 100) if total_distracting > 0 else 0
    return {
        "total_distracting_visits": total_distracting,
        "blocked_visits": blocked,
        "coverage_percent": round(rate, 1),
    }


async def explain_block(conn, domain: str, api_key: str) -> str:
    """Natural-language explanation of why a domain would be blocked."""
    rules = db.get_rules(conn)
    rules_text = "\n".join(f"- {r['text']}" for r in rules)
    prompt = (
        f"Explain briefly why {domain} would be blocked by these rules, or say it wouldn't be:\n"
        f"{rules_text}\n\nKeep it under 2 sentences."
    )
    try:
        return await classifier.call_gemini(api_key, prompt, max_tokens=100)
    except Exception:
        return f"Could not determine — check your rules for {domain}."
