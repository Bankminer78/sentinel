"""FastAPI server — the only thing the GUI and external agents talk to.

Two audiences:
1. The macOS GUI app — the human user
2. External AI agents (the user's personal Claude) — for analysis and automation

Almost every "feature" lives in triggers now. This file is transport + a few
critical primitives the agent can't build itself (OS-level blocking, monitor,
LLM calls, store).
"""
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Any
from pathlib import Path as _StaticPath
from . import (
    db, classifier, monitor, blocker, skiplist, persistence,
    stats as stats_mod, query as query_mod, ai_store, screenshots,
    privacy as privacy_mod, backup as backup_mod, ui,
    triggers as triggers_mod, locks as locks_mod,
    imessage as imessage_mod, notify as notify_mod,
    screen as screen_mod, emergency as emergency_mod,
    audit as audit_mod, sandbox as sandbox_mod,
    primitives as primitives_mod,
    agent as agent_mod, policy_runner as policy_runner_mod,
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
    policy_runner_mod.start()
    # Tell the http_fetch primitive which port we're on so it can refuse
    # the agent calling its own admin endpoints. The CLI passes the port
    # via the SENTINEL_PORT env var; default to 9849.
    import os as _os
    primitives_mod.register_daemon_port(int(_os.environ.get("SENTINEL_PORT", "9849")))


@app.on_event("shutdown")
def shutdown():
    triggers_mod.stop_worker()
    policy_runner_mod.stop()


# --- Web UI: static files ---
_STATIC_DIR = _StaticPath(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def root_ui():
    return FileResponse(_STATIC_DIR / "index.html")


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
    """Receive a page visit from the browser extension.

    Logs EVERY non-skiplisted domain to activity_log so the dashboard
    Activity tab + the agent's reasoning over usage actually have data.
    Previously this only logged blocked visits, which is why the
    activity_log was empty even with the extension installed.

    The decision logic (classify, rule eval, /etc/hosts block) runs in
    parallel — same as before — but is no longer the only path that
    writes a row.
    """
    c = get_conn()
    monitor.set_browser_url(body.url)
    if not body.domain:
        return {"verdict": "allow"}
    if skiplist.should_skip(body.domain):
        return {"verdict": "allow"}

    # Determine the verdict + category for the response.
    verdict = "allow"
    category = None

    if blocker.is_blocked_domain(body.domain):
        verdict = "block"
    else:
        api_key = db.get_config(c, "gemini_api_key")
        if api_key:
            seen = db.get_seen(c, body.domain)
            if seen is None:
                # First time we've seen this domain — classify once + cache.
                # Wrap in try/except: a Gemini timeout / rate limit / network
                # blip must not 500 the activity logger. We just degrade to
                # "allow" + no category.
                try:
                    category = await classifier.classify_domain(api_key, body.domain)
                    db.save_seen(c, body.domain, category)
                except Exception:
                    category = None
            else:
                category = seen
            if category in ("streaming", "social", "adult", "gaming"):
                rules = db.get_rules(c)
                if rules:
                    try:
                        eval_verdict = await classifier.evaluate_rules(
                            api_key, "", body.domain, body.title, rules)
                    except Exception:
                        eval_verdict = "allow"
                    if eval_verdict == "block":
                        blocker.block_domain(body.domain, conn=c, actor="rule_eval")
                        verdict = "block"
                    elif eval_verdict == "warn":
                        verdict = "warn"
                else:
                    # Distracting category but no rules — warn so the user
                    # at least notices the new domain in the dashboard.
                    verdict = "warn"

    # Log every non-skiplisted visit. The dashboard Activity tab reads
    # from this table, and the agent reasons over it via stats.
    db.log_activity(c, "", body.title, body.url, body.domain, verdict)

    response = {"verdict": verdict}
    if category:
        response["category"] = category
    return response


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


# --- Sandbox allowlists (gated by no_modify_allowlist lock) ---
class HttpAllowlistBody(BaseModel):
    hosts: list


class SqlAllowlistBody(BaseModel):
    paths: list


@app.get("/sandbox/http-allowlist")
def get_http_allowlist():
    return {"hosts": sandbox_mod.get_http_allowlist(get_conn())}


@app.post("/sandbox/http-allowlist")
def set_http_allowlist(body: HttpAllowlistBody):
    try:
        sandbox_mod.set_http_allowlist(get_conn(), body.hosts)
        return {"ok": True, "hosts": sandbox_mod.get_http_allowlist(get_conn())}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except PermissionError as e:
        raise HTTPException(423, str(e))


@app.get("/sandbox/sql-allowlist")
def get_sql_allowlist():
    return {"paths": sandbox_mod.get_sql_allowlist(get_conn())}


@app.post("/sandbox/sql-allowlist")
def set_sql_allowlist(body: SqlAllowlistBody):
    try:
        sandbox_mod.set_sql_allowlist(get_conn(), body.paths)
        return {"ok": True, "paths": sandbox_mod.get_sql_allowlist(get_conn())}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except PermissionError as e:
        raise HTTPException(423, str(e))


# --- Audit log (append-only, gated by no_delete_audit lock) ---
@app.get("/audit")
def get_audit(limit: int = 100, primitive: Optional[str] = None,
              actor: Optional[str] = None):
    return audit_mod.list_recent(get_conn(), limit=limit,
                                 primitive=primitive, actor=actor)


@app.get("/audit/count")
def get_audit_count(since: Optional[float] = None):
    return {"count": audit_mod.count(get_conn(), since=since)}


class AuditCleanup(BaseModel):
    older_than_days: int


@app.post("/audit/cleanup")
def post_audit_cleanup(body: AuditCleanup):
    import time
    cutoff = time.time() - max(0, body.older_than_days) * 86400
    result = audit_mod.cleanup_older_than(get_conn(), cutoff)
    if not result.get("ok"):
        raise HTTPException(423, result.get("reason"))
    return result


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


# --- Claude agent surface (Phase 1 of the lockbox refactor) ---

import asyncio as _asyncio
import json as _json
import os as _os_agent
import uuid as _uuid


# Per-session event queues. The POST handler kicks off a background task
# that drains query() messages into the session's queue; the SSE GET handler
# pops events off the queue and writes them to the client. The queue is
# bounded so a runaway agent can't OOM the daemon.
_AGENT_SESSIONS: dict[str, _asyncio.Queue] = {}
_AGENT_SENTINEL = object()  # marks end-of-stream on the queue


def _check_agent_token(authorization: Optional[str]):
    """Reject anything without the per-launch bearer token."""
    expected = _os_agent.environ.get("SENTINEL_AGENT_TOKEN")
    if not expected:
        raise HTTPException(503, "agent token not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    if authorization.removeprefix("Bearer ").strip() != expected:
        raise HTTPException(401, "invalid bearer token")


class AgentRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None


@app.post("/api/agent")
async def agent_start(body: AgentRequest, authorization: Optional[str] = Header(None)):
    """Spawn a Claude session in the background. Returns immediately with
    a session_id; the GUI then opens an SSE connection to /api/agent/{sid}/events
    to stream the reasoning + tool calls + result live."""
    _check_agent_token(authorization)
    if not body.prompt or not body.prompt.strip():
        raise HTTPException(400, "prompt required")

    sid = body.session_id or _uuid.uuid4().hex[:12]
    queue: _asyncio.Queue = _asyncio.Queue(maxsize=200)
    _AGENT_SESSIONS[sid] = queue

    async def _drain():
        try:
            async for event in agent_mod.run_session(body.prompt, session_id=sid, conn=get_conn()):
                try:
                    queue.put_nowait(event)
                except _asyncio.QueueFull:
                    try:
                        queue.get_nowait()
                    except _asyncio.QueueEmpty:
                        pass
                    queue.put_nowait(event)
        except BaseException as e:
            # The SDK's internal TaskGroup can raise ExceptionGroup which
            # extends BaseException and leaks past run_session's handler.
            # If the session already completed (we saw a result event in
            # the queue), this is cleanup noise — don't show it to the
            # user. Only surface real errors from incomplete sessions.
            has_result = any(
                isinstance(item, dict) and item.get("type") == "result"
                for item in list(queue._queue)  # peek without consuming
            ) if hasattr(queue, '_queue') else False
            if not has_result:
                try:
                    queue.put_nowait({
                        "type": "error",
                        "session_id": sid,
                        "error_type": type(e).__name__,
                        "message": str(e)[:500],
                    })
                except Exception:
                    pass
        finally:
            try:
                queue.put_nowait(_AGENT_SENTINEL)
            except _asyncio.QueueFull:
                pass

    _asyncio.create_task(_drain())
    return {"session_id": sid, "events_url": f"/api/agent/{sid}/events"}


@app.get("/api/agent/{session_id}/events")
async def agent_events(session_id: str, authorization: Optional[str] = Header(None)):
    """SSE stream of events for a running agent session.

    Sends ``: keepalive`` comment frames every 5 seconds when the queue is
    idle. Without these, WebKit's fetch().body.getReader() in the WKWebView
    times out long silent gaps (e.g. during a slow tool run) and the GUI
    sees "Stream interrupted: Load failed" mid-session.
    """
    _check_agent_token(authorization)
    queue = _AGENT_SESSIONS.get(session_id)
    if queue is None:
        raise HTTPException(404, "unknown session")

    KEEPALIVE_SEC = 5.0

    async def event_stream():
        try:
            while True:
                try:
                    event = await _asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SEC)
                except _asyncio.TimeoutError:
                    # Idle — send a keepalive comment to keep WKWebView happy
                    yield ": keepalive\n\n"
                    continue
                if event is _AGENT_SENTINEL:
                    yield "event: done\ndata: {}\n\n"
                    return
                yield f"data: {_json.dumps(event, default=str)}\n\n"
        finally:
            _AGENT_SESSIONS.pop(session_id, None)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/agent/budget")
async def agent_budget(authorization: Optional[str] = Header(None)):
    """How much of the daily Claude token budget is left."""
    _check_agent_token(authorization)
    c = get_conn()
    return {
        "budget_usd": agent_mod.get_budget_usd(c),
        "used_usd": agent_mod.get_used_today_usd(c),
        "remaining_usd": agent_mod.remaining_budget_usd(c),
    }
