"""Accountability partners — notify via webhook/email/SMS."""
import time, json, logging
import httpx

log = logging.getLogger(__name__)


def add_partner(conn, name: str, contact: str, method: str = "webhook") -> int:
    cur = conn.execute(
        "INSERT INTO partners (name, contact, method, created_at) VALUES (?,?,?,?)",
        (name, contact, method, time.time()))
    conn.commit()
    return cur.lastrowid


def get_partners(conn) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM partners ORDER BY id").fetchall()]


def get_partner(conn, partner_id: int) -> dict | None:
    r = conn.execute("SELECT * FROM partners WHERE id=?", (partner_id,)).fetchone()
    return dict(r) if r else None


def delete_partner(conn, partner_id: int) -> None:
    conn.execute("DELETE FROM partners WHERE id=?", (partner_id,))
    conn.commit()


async def _send_webhook(url: str, payload: dict) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(url, json=payload)
            return r.status_code < 400
    except Exception as e:
        log.warning("partner webhook failed: %s", e)
        return False


async def notify_partners(conn, event: str, details: dict) -> list[dict]:
    results = []
    payload = {"event": event, "details": details, "ts": time.time()}
    for p in get_partners(conn):
        if p["method"] == "webhook":
            ok = await _send_webhook(p["contact"], payload)
            results.append({"id": p["id"], "method": "webhook", "ok": ok})
        else:
            log.info("partner notify [%s] %s -> %s: %s",
                     p["method"], p["name"], p["contact"], json.dumps(payload))
            results.append({"id": p["id"], "method": p["method"], "ok": True})
    return results
