"""LLM classifier — classifies domains and activities via Gemini Flash."""
import httpx, json, time

_cache = {}  # (domain,) -> (category, timestamp)
CACHE_TTL = 3600  # 1 hour

CLASSIFY_PROMPT = """You are a URL/app categorizer for a website blocker. Classify the domain into EXACTLY ONE category:
- "streaming": Video streaming, piracy, free movies, anime (Netflix, Twitch, TikTok, fmovies, braflix)
- "social": Social media, messaging, forums, memes (YouTube, Instagram, Reddit, Twitter/X, Discord)
- "adult": Pornographic/adult/dating/hookup content
- "gaming": Online games, gaming sites
- "shopping": Shopping, deals, e-commerce beyond essentials
- "none": Utilities, productivity, work, education, dev tools, finance, news, search engines

Respond with ONLY the category name. No explanation.

Domain: {domain}"""

RULE_PARSE_PROMPT = """Parse this natural language rule into a JSON object. The user wants to block or limit certain activities.

Rule: "{text}"

Return a JSON object with these fields (include only relevant ones):
- "domains": list of domain patterns to match (e.g. ["youtube.com", "*.reddit.com"])
- "apps": list of app names to match (e.g. ["Discord", "Steam"])
- "categories": list of categories to match (e.g. ["social", "streaming", "gaming"])
- "schedule": {{"days": "mon-fri"|"sat-sun"|"all", "start": "HH:MM", "end": "HH:MM"}} (when the rule is ACTIVE)
- "action": "block"|"warn"
- "allowed_minutes": number of allowed minutes per day (if the rule allows some usage)

Return ONLY valid JSON, no markdown or explanation."""

EVALUATE_PROMPT = """Given the current activity and active rules, should this activity be blocked?

Current activity:
- App: {app}
- Domain: {domain}
- Window title: {title}
- Time: {time}
- Day: {day}

Active rules:
{rules}

Respond with ONLY one of: "block", "warn", or "allow". No explanation."""


async def call_gemini(api_key: str, prompt: str, max_tokens: int = 50) -> str:
    """Call Gemini Flash API."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0}})
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


async def classify_domain(api_key: str, domain: str) -> str:
    """Classify a domain. Cached."""
    if domain in _cache:
        cat, ts = _cache[domain]
        if time.time() - ts < CACHE_TTL:
            return cat
    result = await call_gemini(api_key, CLASSIFY_PROMPT.format(domain=domain))
    valid = {"streaming", "social", "adult", "gaming", "shopping", "none"}
    category = result.lower() if result.lower() in valid else "none"
    _cache[domain] = (category, time.time())
    return category


async def parse_rule(api_key: str, text: str) -> dict:
    """Parse natural language rule to structured JSON."""
    result = await call_gemini(api_key, RULE_PARSE_PROMPT.format(text=text), max_tokens=300)
    # Strip markdown fences if present
    result = result.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"categories": ["social", "streaming"], "action": "block"}


async def evaluate_rules(api_key: str, app: str, domain: str, title: str, rules: list[dict]) -> str:
    """Evaluate current activity against rules. Returns block/warn/allow."""
    from datetime import datetime
    now = datetime.now()
    rules_text = "\n".join(f"- {r['text']} (parsed: {r['parsed']})" for r in rules)
    prompt = EVALUATE_PROMPT.format(
        app=app, domain=domain or "N/A", title=title or "N/A",
        time=now.strftime("%H:%M"), day=now.strftime("%A"), rules=rules_text)
    result = await call_gemini(api_key, prompt)
    return result.lower() if result.lower() in {"block", "warn", "allow"} else "allow"
