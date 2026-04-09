"""Inbound webhooks — let external services trigger Sentinel actions."""
import hmac, hashlib, secrets, time, uuid


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS webhooks_in (
        id TEXT PRIMARY KEY, name TEXT, secret TEXT,
        action TEXT, created_at REAL
    )""")


def register_webhook(conn, name: str, secret: str, action: str) -> str:
    _ensure_table(conn)
    wid = uuid.uuid4().hex[:16]
    conn.execute(
        "INSERT INTO webhooks_in (id, name, secret, action, created_at) VALUES (?,?,?,?,?)",
        (wid, name, secret, action, time.time()))
    conn.commit()
    return f"/webhooks/in/{wid}"


def list_webhooks(conn) -> list[dict]:
    _ensure_table(conn)
    rows = conn.execute("SELECT * FROM webhooks_in ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]


def get_webhook(conn, webhook_id: str) -> dict | None:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM webhooks_in WHERE id=?", (webhook_id,)).fetchone()
    return dict(r) if r else None


def delete_webhook(conn, webhook_id) -> None:
    _ensure_table(conn)
    conn.execute("DELETE FROM webhooks_in WHERE id=?", (str(webhook_id),))
    conn.commit()


def verify_webhook(conn, webhook_id: str, signature: str, body: bytes) -> bool:
    w = get_webhook(conn, webhook_id)
    if not w:
        return False
    expected = hmac.new(w["secret"].encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


async def handle_webhook(conn, webhook_id: str, payload: dict) -> dict:
    w = get_webhook(conn, webhook_id)
    if not w:
        return {"ok": False, "error": "not_found"}
    action = w["action"]
    result = {"ok": True, "action": action, "webhook": w["name"]}
    if action == "start_focus":
        from . import scheduler
        mins = int(payload.get("minutes", 25))
        scheduler.start_focus(conn, duration_minutes=mins, locked=False) \
            if hasattr(scheduler, "start_focus") else None
        result["started_minutes"] = mins
    elif action == "notify":
        from . import notifications
        notifications.notify_macos(w["name"], str(payload.get("message", "")))
    elif action == "log":
        result["logged"] = payload
    else:
        result["ok"] = False
        result["error"] = "unknown_action"
    return result


def rotate_secret(conn, webhook_id) -> str:
    _ensure_table(conn)
    new_secret = secrets.token_hex(24)
    conn.execute("UPDATE webhooks_in SET secret=? WHERE id=?", (new_secret, str(webhook_id)))
    conn.commit()
    return new_secret
