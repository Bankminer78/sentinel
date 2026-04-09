"""Cross-device sync — push/pull state to a remote sync server."""
import json, logging, uuid
import httpx

from sentinel import db, importer

log = logging.getLogger(__name__)


def set_device_id(conn, device_id: str) -> None:
    db.set_config(conn, "sync_device_id", device_id)


def get_device_id(conn) -> str:
    did = db.get_config(conn, "sync_device_id")
    if not did:
        did = uuid.uuid4().hex[:12]
        set_device_id(conn, did)
    return did


def set_sync_url(conn, url: str) -> None:
    db.set_config(conn, "sync_url", url)


def get_sync_url(conn) -> str:
    return db.get_config(conn, "sync_url") or ""


def _snapshot(conn) -> dict:
    snap = importer.export_all(conn)
    rows = conn.execute("SELECT domain, category, first_seen FROM seen_domains").fetchall()
    snap["seen_domains"] = [
        {"domain": r["domain"], "category": r["category"], "first_seen": r["first_seen"]}
        for r in rows
    ]
    return snap


def _merge_seen(conn, seen: list) -> int:
    n = 0
    for s in seen or []:
        if not isinstance(s, dict) or not s.get("domain"):
            continue
        existing = conn.execute(
            "SELECT 1 FROM seen_domains WHERE domain=?", (s["domain"],)).fetchone()
        if existing:
            continue
        conn.execute(
            "INSERT INTO seen_domains (domain,category,first_seen) VALUES (?,?,?)",
            (s["domain"], s.get("category"), s.get("first_seen") or 0))
        n += 1
    conn.commit()
    return n


async def push_to_sync(conn, sync_url: str, device_id: str) -> dict:
    """Push local state to sync server."""
    payload = {"device_id": device_id, "data": _snapshot(conn)}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{sync_url.rstrip('/')}/sync/push", json=payload)
            if r.status_code >= 400:
                return {"ok": False, "error": f"status {r.status_code}"}
            return {"ok": True, "pushed": len(payload["data"].get("rules", []))}
    except Exception as e:
        log.warning("sync push failed: %s", e)
        return {"ok": False, "error": str(e)}


async def pull_from_sync(conn, sync_url: str, device_id: str) -> dict:
    """Pull remote state, merge into local."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{sync_url.rstrip('/')}/sync/pull", params={"device_id": device_id})
            if r.status_code >= 400:
                return {"ok": False, "error": f"status {r.status_code}"}
            data = r.json()
    except Exception as e:
        log.warning("sync pull failed: %s", e)
        return {"ok": False, "error": str(e)}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return {"ok": False, "error": "bad json"}
    payload = data.get("data", data) if isinstance(data, dict) else {}
    counts = importer.import_all(conn, payload)
    counts["seen_domains"] = _merge_seen(conn, payload.get("seen_domains", []))
    counts["ok"] = True
    return counts
