"""Automated triggers — run actions on events."""
import time, json
from . import db

EVENTS = ["rule_violated", "goal_missed", "streak_broken", "focus_started",
          "focus_ended", "pomodoro_done", "achievement_unlocked", "morning", "evening"]
ACTIONS = ["notify", "block_domain", "start_pomodoro", "log_activity",
           "post_webhook", "run_shell", "add_penalty", "send_slack"]


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS triggers (
        id INTEGER PRIMARY KEY, event TEXT, action TEXT,
        params TEXT, active INTEGER DEFAULT 1, created_at REAL
    )""")


def create_trigger(conn, event: str, action: str, params: dict) -> int:
    _ensure_table(conn)
    if event not in EVENTS:
        raise ValueError(f"unknown event: {event}")
    if action not in ACTIONS:
        raise ValueError(f"unknown action: {action}")
    cur = conn.execute(
        "INSERT INTO triggers (event, action, params, active, created_at) VALUES (?,?,?,1,?)",
        (event, action, json.dumps(params or {}), time.time()))
    conn.commit()
    return cur.lastrowid


def get_triggers(conn, event: str = None) -> list:
    _ensure_table(conn)
    if event:
        rows = conn.execute(
            "SELECT * FROM triggers WHERE event=? ORDER BY id", (event,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM triggers ORDER BY id").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["params"] = json.loads(d["params"]) if d["params"] else {}
        out.append(d)
    return out


def delete_trigger(conn, trigger_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM triggers WHERE id=?", (trigger_id,))
    conn.commit()


def toggle_trigger(conn, trigger_id: int):
    _ensure_table(conn)
    conn.execute("UPDATE triggers SET active = NOT active WHERE id=?", (trigger_id,))
    conn.commit()


async def _run_action(conn, action: str, params: dict, context: dict) -> dict:
    merged = {**params, **(context or {})}
    if action == "notify":
        from . import notifications
        ok = notifications.notify_macos(
            merged.get("title", "Sentinel"), merged.get("message", ""))
        return {"ok": bool(ok)}
    if action == "send_slack":
        from . import notifications
        url = merged.get("webhook_url") or db.get_config(conn, "slack_webhook")
        if not url:
            return {"ok": False, "error": "no webhook"}
        return {"ok": await notifications.notify_slack(url, merged.get("text", ""))}
    if action == "post_webhook":
        from . import notifications
        return {"ok": await notifications.notify_webhook(
            merged.get("url", ""), merged.get("payload", {}))}
    if action == "log_activity":
        db.log_activity(conn, merged.get("app", "trigger"),
                        merged.get("title", ""), None, None, "trigger")
        return {"ok": True}
    if action == "add_penalty":
        conn.execute("INSERT INTO penalties (rule_id, amount, created_at) VALUES (?,?,?)",
                     (merged.get("rule_id"), float(merged.get("amount", 0)), time.time()))
        conn.commit()
        return {"ok": True}
    return {"ok": False, "error": f"unsupported: {action}"}


async def fire_event(conn, event: str, context: dict = None) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM triggers WHERE event=? AND active=1", (event,)).fetchall()
    results = []
    for r in rows:
        params = json.loads(r["params"]) if r["params"] else {}
        res = await _run_action(conn, r["action"], params, context or {})
        results.append({"trigger_id": r["id"], "action": r["action"], "result": res})
    return results
