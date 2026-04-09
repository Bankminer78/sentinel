"""Periodic screenshot analysis via Gemini vision."""
import subprocess, base64, json, threading, time, httpx

_vision_thread = None
_vision_running = False
_last_verdict = {"verdict": "neutral", "details": "", "ts": 0}

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


async def monitor_with_vision(conn, api_key: str, interval: int = 120) -> dict:
    """Single vision check — stores verdict and returns it."""
    global _last_verdict
    result = await capture_and_analyze(api_key, "")
    result["ts"] = time.time()
    _last_verdict = result
    return result


def start_vision_monitor(conn, api_key: str, interval: int = 120):
    """Background thread that periodically captures + analyzes."""
    global _vision_thread, _vision_running
    if _vision_running:
        return
    _vision_running = True

    def _loop():
        import asyncio
        while _vision_running:
            try:
                asyncio.run(monitor_with_vision(conn, api_key, interval))
            except Exception:
                pass
            for _ in range(interval):
                if not _vision_running:
                    break
                time.sleep(1)

    _vision_thread = threading.Thread(target=_loop, daemon=True)
    _vision_thread.start()


def stop_vision_monitor():
    global _vision_running
    _vision_running = False


def is_vision_active() -> bool:
    return _vision_running


def get_last_verdict() -> dict:
    return dict(_last_verdict)
