"""One-shot screenshot + Gemini vision wrapper.

This module exists for the ``POST /vision/snapshot`` REST endpoint, which
gives the GUI (and external Claude) a synchronous way to test vision
without authoring a trigger. Inside trigger recipes, the agent should use
the ``vision_check`` macro instead — it desugars to screen_capture +
http_fetch + jsonpath via the new primitive layer.

The background-monitor thread that used to live here was unused dead
code (no caller in the daemon and the trigger system handles scheduling).
Removed in Phase 5 of the primitive refactor.
"""
import base64, json, subprocess
import httpx


VISION_PROMPT = (
    "Look at this screenshot. Is the user doing productive work or getting distracted? "
    "Context: {user_context}. "
    'Respond with JSON: {{"verdict": "productive|distracted|neutral", "details": "brief description"}}'
)


def take_screenshot(path: str = "/tmp/sentinel_shot.png") -> bool:
    """Capture a screenshot via macOS screencapture. Returns True on success."""
    try:
        r = subprocess.run(["screencapture", "-x", path], timeout=5)
        return r.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


async def analyze_screenshot(image_path: str, api_key: str, prompt: str) -> str:
    """Send a screenshot to Gemini vision, return raw text response."""
    try:
        with open(image_path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
    except OSError:
        return ""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}",
            json={"contents": [{"parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": data}}]}],
                  "generationConfig": {"maxOutputTokens": 200, "temperature": 0}})
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def _parse_verdict(raw: str) -> dict:
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return {"verdict": "neutral", "details": raw[:120]}
    verdict = str(obj.get("verdict", "neutral")).lower()
    if verdict not in ("productive", "distracted", "neutral"):
        verdict = "neutral"
    return {"verdict": verdict, "details": str(obj.get("details", ""))[:200]}


async def capture_and_analyze(api_key: str, user_context: str = "") -> dict:
    """Take a screenshot, send to Gemini vision, return parsed verdict."""
    path = "/tmp/sentinel_screenshot.png"
    if not take_screenshot(path):
        return {"verdict": "neutral", "details": "capture failed"}
    raw = await analyze_screenshot(path, api_key, VISION_PROMPT.format(user_context=user_context or "none"))
    if not raw:
        return {"verdict": "neutral", "details": "no response"}
    return _parse_verdict(raw)
