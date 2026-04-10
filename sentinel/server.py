"""FastAPI server — the only thing the GUI and external agents talk to.

Two audiences:
1. The macOS GUI app — the human user
2. External AI agents (the user's personal Claude) — for analysis and automation

Almost every "feature" lives in triggers now. This file is transport + a few
critical primitives the agent can't build itself (OS-level blocking, monitor,
LLM calls, store).
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, Any
from . import (
    db, classifier, monitor, blocker, skiplist, persistence,
    stats as stats_mod, query as query_mod, ai_store, screenshots,
    privacy as privacy_mod, backup as backup_mod, ui,
    triggers as triggers_mod, locks as locks_mod,
    imessage as imessage_mod, notify as notify_mod,
    screen as screen_mod, emergency as emergency_mod,
)

app = FastAPI(title="Sentinel")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
conn = None


def get_conn():
    global conn
    if conn is None:
        conn = db.connect()
    return conn


@app.on_event("startup")
def startup():
    global conn
    conn = db.connect()
    monitor.start()
    persistence.start_watcher()
    triggers_mod.start_worker(conn)


@app.on_event("shutdown")
def shutdown():
    triggers_mod.stop_worker()


# --- Web UI ---
@app.get("/", response_class=HTMLResponse)
def root_ui():
    return ui.get_ui_html()


# --- Health ---
@app.get("/health")
def health():
    c = get_conn()
    return {
        "ok": True,
        "rules": len(db.get_rules(c, active_only=False)),
        "api_key_set": bool(db.get_config(c, "gemini_api_key")),
    }


# --- Config ---
class ConfigSet(BaseModel):
    key: str
    value: str


@app.post("/config")
def set_config(body: ConfigSet):
    db.set_config(get_conn(), body.key, body.value)
    return {"ok": True}


@app.get("/config/{key}")
def get_config(key: str):
    return {"value": db.get_config(get_conn(), key)}


# --- Rules ---
class RuleCreate(BaseModel):
    text: str


@app.post("/rules")
async def create_rule(body: RuleCreate):
    c = get_conn()
    api_key = db.get_config(c, "gemini_api_key")
    parsed = {}
    if api_key:
        try:
            parsed = await classifier.parse_rule(api_key, body.text)
        except Exception:
            parsed = {}
    rule_id = db.add_rule(c, body.text, parsed)
    return {"id": rule_id, "text": body.text, "parsed": parsed}


@app.get("/rules")
def list_rules():
    return db.get_rules(get_conn(), active_only=False)


@app.delete("/rules/{rule_id}")
def remove_rule(rule_id: int):
    db.delete_rule(get_conn(), rule_id)
    return {"ok": True}


@app.post("/rules/{rule_id}/toggle")
def toggle_rule(rule_id: int):
    db.toggle_rule(get_conn(), rule_id)
    return {"ok": True}


# --- Activity ---
class ActivityReport(BaseModel):
    url: str = ""
    title: str = ""
    domain: str = ""


@app.post("/activity")
async def report_activity(body: ActivityReport):
    c = get_conn()
    monitor.set_browser_url(body.url)
    if not body.domain:
        return {"verdict": "allow"}
    if skiplist.should_skip(body.domain):
        return {"verdict": "allow"}
    if blocker.is_blocked_domain(body.domain):
        return {"verdict": "block"}
    api_key = db.get_config(c, "gemini_api_key")
    if not api_key:
        return {"verdict": "allow"}
    seen = db.get_seen(c, body.domain)
    if seen in ("none", "approved"):
        return {"verdict": "allow"}
    if not seen:
        category = await classifier.classify_domain(api_key, body.domain)
        db.save_seen(c, body.domain, category)
        if category in ("streaming", "social", "adult", "gaming"):
            rules = db.get_rules(c)
            if rules:
                verdict = await classifier.evaluate_rules(api_key, "", body.domain, body.title, rules)
                if verdict == "block":
                    blocker.block_domain(body.domain)
                    db.log_activity(c, "", body.title, body.url, body.domain, "block")
                    return {"verdict": "block", "category": category}
            return {"verdict": "warn", "category": category}
        return {"verdict": "allow"}
    if seen in ("streaming", "social", "adult", "gaming"):
        rules = db.get_rules(c)
        if rules:
            verdict = await classifier.evaluate_rules(api_key, "", body.domain, body.title, rules)
            return {"verdict": verdict, "category": seen}
    return {"verdict": "allow"}


@app.get("/status")
def status():
    c = get_conn()
    return {
        "current": monitor.get_current(),
        "rules": db.get_rules(c),
        "blocked": blocker.get_blocked(),
    }


@app.get("/activities")
def get_activities(limit: int = 100, since: Optional[float] = None):
    return db.get_activities(get_conn(), since=since, limit=limit)


# --- Stats (views over the activity log) ---
@app.get("/stats")
def stats():
    c = get_conn()
    return {
        "score": stats_mod.calculate_score(c),
        "breakdown": stats_mod.get_daily_breakdown(c),
        "top_distractions": stats_mod.get_top_distractions(c, days=7, limit=10),
    }


# --- Blocking control ---
@app.post("/block/{domain}")
def manual_block(domain: str):
    blocker.block_domain(domain)
    return {"ok": True}


@app.delete("/block/{domain}")
def manual_unblock(domain: str):
    if not blocker.unblock_domain(domain, conn=get_conn()):
        raise HTTPException(423, {
            "message": "domain is locked — cannot unblock until lock expires",
            "locks": locks_mod.list_active(get_conn(), kind="no_unblock_domain"),
        })
    return {"ok": True}


@app.get("/blocked")
def blocked_list():
    return blocker.get_blocked()


# --- Vision primitive (agent calls this from triggers) ---
class VisionSnap(BaseModel):
    user_context: str = ""


@app.post("/vision/snapshot")
async def vision_snapshot(body: VisionSnap):
    c = get_conn()
    api_key = db.get_config(c, "gemini_api_key")
    if not api_key:
        raise HTTPException(400, "API key not set")
    return await screenshots.capture_and_analyze(api_key, body.user_context)


# --- AI Q&A ---
class AskBody(BaseModel):
    question: str


@app.post("/ask")
async def ask(body: AskBody):
    c = get_conn()
    api_key = db.get_config(c, "gemini_api_key")
    if not api_key:
        raise HTTPException(400, "API key not set")
    return {"answer": await query_mod.ask(c, body.question, api_key)}


# --- AI Store ---
class KVSet(BaseModel):
    namespace: str
    key: str
    value: Any


@app.post("/ai/kv")
def ai_kv_set(body: KVSet):
    ai_store.kv_set(get_conn(), body.namespace, body.key, body.value)
    return {"ok": True}


@app.get("/ai/kv/{namespace}/{key}")
def ai_kv_get(namespace: str, key: str):
    return {"value": ai_store.kv_get(get_conn(), namespace, key)}


@app.delete("/ai/kv/{namespace}/{key}")
def ai_kv_delete(namespace: str, key: str):
    ai_store.kv_delete(get_conn(), namespace, key)
    return {"ok": True}


@app.get("/ai/kv/{namespace}")
def ai_kv_list(namespace: str):
    return ai_store.kv_list(get_conn(), namespace)


@app.get("/ai/namespaces")
def ai_namespaces():
    c = get_conn()
    return {"kv": ai_store.kv_namespaces(c), "docs": ai_store.doc_namespaces(c)}


class DocAdd(BaseModel):
    namespace: str
    doc: Any
    tags: list = []


@app.post("/ai/docs")
def ai_doc_add(body: DocAdd):
    return {"id": ai_store.doc_add(get_conn(), body.namespace, body.doc, body.tags)}


@app.get("/ai/docs")
def ai_doc_list(namespace: str = None, limit: int = 100, since: float = None):
    return ai_store.doc_list(get_conn(), namespace=namespace, limit=limit, since=since)


@app.get("/ai/docs/{doc_id}")
def ai_doc_get(doc_id: int):
    d = ai_store.doc_get(get_conn(), doc_id)
    if not d:
        raise HTTPException(404, "not found")
    return d


@app.delete("/ai/docs/{doc_id}")
def ai_doc_delete(doc_id: int):
    ai_store.doc_delete(get_conn(), doc_id)
    return {"ok": True}


@app.get("/ai/search")
def ai_search(q: str, namespace: str = None, limit: int = 50):
    return ai_store.doc_search(get_conn(), q, namespace=namespace, limit=limit)


@app.get("/ai/summary")
def ai_summary():
    return ai_store.summary(get_conn())


# --- Privacy (one config key, gated on the hot path) ---
class PrivacyLevel(BaseModel):
    level: str


@app.get("/privacy")
def privacy_get():
    return {"level": privacy_mod.get_level(get_conn())}


@app.post("/privacy")
def privacy_set(body: PrivacyLevel):
    privacy_mod.set_level(get_conn(), body.level)
    return {"ok": True}


# --- Backup ---
@app.post("/backup")
def backup_create():
    return {"path": backup_mod.create_backup(get_conn())}


@app.get("/backups")
def backups_list():
    return backup_mod.list_backups()


# --- Triggers (AI-authored features) ---
class TriggerCreate(BaseModel):
    name: str
    interval_sec: int = 300
    description: str = ""
    recipe: dict


class TriggerAuthor(BaseModel):
    request: str
    test: bool = True
    max_revisions: int = 2


@app.post("/triggers")
def triggers_create(body: TriggerCreate):
    try:
        tid = triggers_mod.create(get_conn(), body.name, body.recipe,
                                  interval_sec=body.interval_sec,
                                  description=body.description)
        return {"id": tid, "name": body.name}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/triggers")
def triggers_list():
    return triggers_mod.list_all(get_conn())


@app.get("/triggers/calls")
def triggers_calls():
    return triggers_mod.list_calls()


@app.get("/triggers/{name}")
def triggers_get(name: str):
    t = triggers_mod.get(get_conn(), name)
    if not t:
        raise HTTPException(404, "not found")
    return t


@app.delete("/triggers/{name}")
def triggers_delete(name: str):
    if not triggers_mod.delete(get_conn(), name):
        raise HTTPException(423, "trigger is locked — cannot delete until lock expires")
    return {"ok": True}


@app.post("/triggers/{name}/toggle")
def triggers_toggle(name: str):
    t = triggers_mod.get(get_conn(), name)
    if not t:
        raise HTTPException(404, "not found")
    new = not bool(t.get("enabled"))
    if not triggers_mod.set_enabled(get_conn(), name, new):
        raise HTTPException(423, "trigger is locked — cannot disable until lock expires")
    return {"ok": True, "enabled": new}


@app.post("/triggers/{name}/run")
def triggers_run(name: str):
    return triggers_mod.run_once(get_conn(), name)


@app.get("/triggers/{name}/runs")
def triggers_runs(name: str, limit: int = 10):
    return triggers_mod.list_runs(get_conn(), name, limit=limit)


@app.get("/triggers/{name}/health")
def triggers_health(name: str):
    return triggers_mod.health(get_conn(), name)


# --- iMessage sensor ---
@app.get("/imessage/access")
def imessage_access():
    return imessage_mod.access_status()


@app.get("/imessage/current")
def imessage_current():
    return imessage_mod.current_chat()


@app.get("/imessage/recent-chats")
def imessage_recent_chats(limit: int = 10):
    return imessage_mod.recent_chats(limit=limit)


@app.get("/imessage/recent-messages")
def imessage_recent_messages(handle: str, limit: int = 20):
    return imessage_mod.recent_messages(handle, limit=limit)


# --- Notify / dialog effectors ---
class NotifyBody(BaseModel):
    title: str = "Sentinel"
    body: str = ""
    subtitle: str = ""


class DialogBody(BaseModel):
    title: str = "Sentinel"
    body: str = ""
    buttons: list = ["OK"]
    default_button: Optional[str] = None
    timeout_seconds: Optional[int] = None


@app.post("/notify")
def post_notify(body: NotifyBody):
    return notify_mod.notify(body.title, body.body, body.subtitle)


@app.post("/dialog")
def post_dialog(body: DialogBody):
    return notify_mod.dialog(body.title, body.body, body.buttons,
                             body.default_button, body.timeout_seconds)


# --- Frozen Turkey: screen lockout ---
class ScreenLockBody(BaseModel):
    duration_seconds: int
    message: str = "Focus mode"


@app.post("/screen-lock")
def post_screen_lock(body: ScreenLockBody):
    try:
        return screen_mod.lock(get_conn(), body.duration_seconds, body.message)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/screen-lock/state")
def get_screen_lock_state():
    """Polled by the macOS app every second to know whether to take over."""
    return screen_mod.get_state(get_conn())


# --- Emergency exit ---
class EmergencyExitBody(BaseModel):
    reason: str
    kinds: Optional[list] = None


@app.get("/emergency-exit/status")
def emergency_status():
    return emergency_mod.status(get_conn())


@app.get("/emergency-exit/history")
def emergency_history(limit: int = 20):
    return emergency_mod.history(get_conn(), limit=limit)


@app.post("/emergency-exit")
def emergency_exit(body: EmergencyExitBody):
    result = emergency_mod.trigger(get_conn(), body.reason, body.kinds)
    if not result.get("ok"):
        raise HTTPException(429 if "remaining" in result.get("error", "")
                            else 400, result.get("error"))
    return result


# --- Locks (commitments + friction-gated early release) ---
class LockCreate(BaseModel):
    name: str
    kind: str
    target: Optional[str] = None
    duration_seconds: int
    friction: Optional[dict] = None


class ChallengeResponse(BaseModel):
    token: str
    response: Optional[str] = None


@app.post("/locks")
def locks_create(body: LockCreate):
    try:
        lid = locks_mod.create(get_conn(), body.name, body.kind, body.target,
                               body.duration_seconds, body.friction)
        return {"id": lid, "name": body.name, "kind": body.kind}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/locks")
def locks_list(kind: Optional[str] = None, include_inactive: bool = False):
    if include_inactive:
        return locks_mod.list_all(get_conn())
    return locks_mod.list_active(get_conn(), kind=kind)


@app.get("/locks/{lock_id}")
def locks_get(lock_id: int):
    lk = locks_mod.get(get_conn(), lock_id)
    if not lk:
        raise HTTPException(404, "not found")
    return lk


@app.delete("/locks/{lock_id}")
def locks_delete(lock_id: int):
    if not locks_mod.delete(get_conn(), lock_id):
        raise HTTPException(423, "lock is still active — cannot delete")
    return {"ok": True}


@app.post("/locks/{lock_id}/release")
def locks_request_release(lock_id: int):
    return locks_mod.request_release(get_conn(), lock_id)


@app.post("/locks/{lock_id}/complete")
def locks_complete_release(lock_id: int, body: ChallengeResponse):
    return locks_mod.complete_release(get_conn(), lock_id, body.token, body.response)


@app.post("/triggers/author")
async def triggers_author(body: TriggerAuthor):
    """Plain English → trigger recipe via the internal Gemini agent.

    By default, test-runs the recipe and revises on failure (up to
    body.max_revisions times). Set test=false to skip the feedback loop.
    """
    import httpx
    c = get_conn()
    api_key = db.get_config(c, "gemini_api_key")
    if not api_key:
        raise HTTPException(400, "API key not set")
    try:
        if body.test:
            result = await triggers_mod.author_and_test(
                c, api_key, body.request, max_revisions=body.max_revisions)
            if not result["ok"]:
                raise HTTPException(422, {
                    "message": "trigger failed test-run after revisions",
                    "history": result["history"],
                    "last_error": result.get("error"),
                    "test_run": result.get("test_run"),
                })
            return result
        else:
            spec = await triggers_mod.author_from_text(api_key, body.request)
            tid = triggers_mod.create(c, spec["name"], spec["recipe"],
                                      interval_sec=int(spec.get("interval_sec", 300)),
                                      description=spec.get("description", ""))
            return {"ok": True, "id": tid, "spec": spec}
    except ValueError as e:
        raise HTTPException(400, f"author failed: {e}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"LLM upstream error: {e.response.status_code}")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"LLM network error: {e}")
