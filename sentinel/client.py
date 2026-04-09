"""Python client for Sentinel API."""
import httpx


class SentinelClient:
    def __init__(self, base_url: str = "http://localhost:9849"):
        self.base_url = base_url.rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    async def _get(self, path: str, **kw):
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(self._url(path), **kw)
            r.raise_for_status()
            return r.json()

    async def _post(self, path: str, json=None):
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(self._url(path), json=json or {})
            r.raise_for_status()
            return r.json()

    async def _delete(self, path: str):
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.delete(self._url(path))
            r.raise_for_status()
            return r.json()

    async def add_rule(self, text: str) -> dict:
        return await self._post("/rules", {"text": text})

    async def list_rules(self) -> list:
        return await self._get("/rules")

    async def delete_rule(self, rule_id: int):
        return await self._delete(f"/rules/{rule_id}")

    async def toggle_rule(self, rule_id: int):
        return await self._post(f"/rules/{rule_id}/toggle")

    async def status(self) -> dict:
        return await self._get("/status")

    async def stats(self) -> dict:
        return await self._get("/stats")

    async def block(self, domain: str):
        return await self._post(f"/block/domain/{domain}")

    async def unblock(self, domain: str):
        return await self._delete(f"/block/domain/{domain}")

    async def start_focus(self, minutes: int, locked: bool = False):
        return await self._post("/focus/start",
                                {"duration_minutes": minutes, "locked": locked})

    async def start_pomodoro(self, work: int = 25, br: int = 5):
        return await self._post("/pomodoro/start",
                                {"work_minutes": work, "break_minutes": br})

    async def get_score(self) -> float:
        data = await self._get("/stats/score")
        return float(data.get("score", 0.0))

    async def ask(self, question: str) -> str:
        data = await self._post("/ask", {"question": question})
        return data.get("answer", "")

    async def add_goal(self, name: str, target_type: str, value: int):
        return await self._post("/goals", {
            "name": name, "target_type": target_type, "target_value": value})
