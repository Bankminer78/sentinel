"""Sentinel SDK — Python library for building integrations."""
import httpx, asyncio


class Sentinel:
    """Sync/async SDK for Sentinel's HTTP API."""

    def __init__(self, base_url: str = "http://localhost:9849", api_key: str = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._headers = {"Content-Type": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    # --- Sync methods ---
    def get(self, path: str) -> dict:
        with httpx.Client(timeout=10) as c:
            return c.get(self._url(path), headers=self._headers).json()

    def post(self, path: str, data: dict = None) -> dict:
        with httpx.Client(timeout=10) as c:
            return c.post(self._url(path), headers=self._headers, json=data or {}).json()

    def delete(self, path: str) -> dict:
        with httpx.Client(timeout=10) as c:
            return c.delete(self._url(path), headers=self._headers).json()

    # --- Convenience methods ---
    def add_rule(self, text: str) -> dict:
        return self.post("/rules", {"text": text})

    def list_rules(self) -> list:
        return self.get("/rules")

    def status(self) -> dict:
        return self.get("/status")

    def score(self) -> float:
        return self.get("/stats/score").get("score", 0)

    def start_focus(self, minutes: int = 60, locked: bool = False) -> dict:
        return self.post("/focus/start", {"duration_minutes": minutes, "locked": locked})

    def start_pomodoro(self, work: int = 25, break_min: int = 5) -> dict:
        return self.post("/pomodoro/start", {"work_minutes": work, "break_minutes": break_min})

    def block(self, domain: str) -> dict:
        return self.post(f"/block/domain/{domain}")

    def log_mood(self, mood: int, note: str = "") -> dict:
        return self.post("/mood", {"mood": mood, "note": note})

    def log_water(self, ounces: float = 8) -> dict:
        return self.post("/wellness/water", {"ounces": ounces})

    def add_habit(self, name: str) -> dict:
        return self.post("/habits", {"name": name})

    def log_habit(self, habit_id: int) -> dict:
        return self.post(f"/habits/{habit_id}/log", {})

    def add_goal(self, name: str, target_type: str, value: int) -> dict:
        return self.post("/goals", {"name": name, "target_type": target_type, "target_value": value})

    def achievements(self) -> list:
        return self.get("/achievements/unlocked")

    def level(self) -> dict:
        return self.get("/points/level")


# Quick singleton access
_default = None


def client(base_url: str = "http://localhost:9849") -> Sentinel:
    global _default
    if _default is None or _default.base_url != base_url:
        _default = Sentinel(base_url)
    return _default
