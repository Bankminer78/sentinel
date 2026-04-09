"""FastAPI server — the only thing the GUI and external agents talk to.

Two audiences:
1. The macOS GUI app — the human user
2. External AI agents (the user's personal Claude) — for analysis and automation
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, Any
from . import (
    db, classifier, monitor, blocker, skiplist, scheduler, interventions,
    persistence, stats as stats_mod, query as query_mod, ai_store,
    chat_history, screenshots, search as search_mod, privacy as privacy_mod,
    audit as audit_mod, backup as backup_mod, cache, ui, triggers as triggers_mod,
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
    audit_mod.log_action(c, "rule.create", {"id": rule_id, "text": body.text})
    return {"id": rule_id, "text": body.text, "parsed": parsed}


@app.get("/rules")
def list_rules():
    return db.get_rules(get_conn(), active_only=False)


@app.delete("/rules/{rule_id}")
def remove_rule(rule_id: int):
    db.delete_rule(get_conn(), rule_id)
    audit_mod.log_action(get_conn(), "rule.delete", {"id": rule_id})
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


# --- Stats ---
@app.get("/stats")
def stats():
    c = get_conn()
    return {
        "score": stats_mod.calculate_score(c),
        "breakdown": stats_mod.get_daily_breakdown(c),
        "top_distractions": stats_mod.get_top_distractions(c, days=7, limit=10),
    }


@app.get("/stats/score")
def stats_score():
    return {"score": stats_mod.calculate_score(get_conn())}


@app.get("/stats/week")
def stats_week():
    return stats_mod.get_week_summary(get_conn())


@app.get("/stats/month")
def stats_month():
    return stats_mod.get_month_summary(get_conn())


@app.get("/stats/top-distractions")
def stats_top(days: int = 7, limit: int = 10):
    return stats_mod.get_top_distractions(get_conn(), days=days, limit=limit)


# --- Blocking control ---
@app.post("/block/{domain}")
def manual_block(domain: str):
    blocker.block_domain(domain)
    audit_mod.log_action(get_conn(), "block.manual", {"domain": domain})
    return {"ok": True}


@app.delete("/block/{domain}")
def manual_unblock(domain: str):
    blocker.unblock_domain(domain)
    return {"ok": True}


@app.get("/blocked")
def blocked_list():
    return blocker.get_blocked()


# --- Pomodoro / Focus ---
class PomodoroStart(BaseModel):
    work_minutes: int = 25
    break_minutes: int = 5
    cycles: int = 4


@app.post("/pomodoro/start")
def pomodoro_start(body: PomodoroStart):
    return scheduler.start_pomodoro(get_conn(), body.work_minutes, body.break_minutes, body.cycles)


@app.get("/pomodoro")
def pomodoro_state():
    return scheduler.get_pomodoro_state(get_conn()) or {}


@app.delete("/pomodoro")
def pomodoro_stop():
    scheduler.stop_pomodoro(get_conn())
    return {"ok": True}


class FocusStart(BaseModel):
    duration_minutes: int = 60
    locked: bool = True


@app.post("/focus/start")
def focus_start(body: FocusStart):
    return scheduler.start_focus_session(get_conn(), body.duration_minutes, body.locked)


@app.get("/focus")
def focus_status():
    return scheduler.get_focus_session(get_conn()) or {}


@app.delete("/focus/{session_id}")
def focus_end(session_id: int, force: bool = False):
    return {"ok": scheduler.end_focus_session(get_conn(), session_id, force=force)}


# --- AI Q&A ---
class AskBody(BaseModel):
    question: str


@app.post("/ask")
async def ask(body: AskBody):
    c = get_conn()
    api_key = db.get_config(c, "gemini_api_key")
    if not api_key:
        raise HTTPException(400, "API key not set")
    answer = await query_mod.ask(c, body.question, api_key)
    return {"answer": answer}


# --- AI Store: KV ---
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


# --- AI Store: Docs ---
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


# --- Chat history ---
class ChatCreate(BaseModel):
    title: str = "New chat"


class ChatMessage(BaseModel):
    session_id: int
    role: str
    content: str


@app.post("/chat/sessions")
def chat_create(body: ChatCreate):
    return {"id": chat_history.create_session(get_conn(), body.title)}


@app.get("/chat/sessions")
def chat_list():
    return chat_history.list_sessions(get_conn())


@app.get("/chat/sessions/{sid}")
def chat_get(sid: int):
    return chat_history.get_session(get_conn(), sid) or {}


@app.delete("/chat/sessions/{sid}")
def chat_delete(sid: int):
    chat_history.delete_session(get_conn(), sid)
    return {"ok": True}


@app.post("/chat/messages")
def chat_msg(body: ChatMessage):
    return {"id": chat_history.add_message(get_conn(), body.session_id, body.role, body.content)}


# --- Search ---
@app.get("/search")
def search(q: str):
    return search_mod.search_all(get_conn(), q)


# --- Privacy ---
class PrivacyLevel(BaseModel):
    level: str


@app.get("/privacy")
def privacy_get():
    c = get_conn()
    return {"level": privacy_mod.get_privacy_level(c), "config": privacy_mod.get_privacy_config(c)}


@app.post("/privacy")
def privacy_set(body: PrivacyLevel):
    privacy_mod.set_privacy_level(get_conn(), body.level)
    return {"ok": True}


# --- Audit ---
@app.get("/audit")
def audit_log(limit: int = 100):
    return audit_mod.get_audit_log(get_conn(), limit)


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


@app.post("/triggers")
def triggers_create(body: TriggerCreate):
    try:
        tid = triggers_mod.create(get_conn(), body.name, body.recipe,
                                  interval_sec=body.interval_sec,
                                  description=body.description)
        audit_mod.log_action(get_conn(), "trigger.create",
                             {"name": body.name, "id": tid})
        return {"id": tid, "name": body.name}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/triggers")
def triggers_list():
    return triggers_mod.list_all(get_conn())


@app.get("/triggers/calls")
def triggers_calls():
    """The operations triggers can call. Used by the LLM author too."""
    return triggers_mod.list_calls()


@app.get("/triggers/{name}")
def triggers_get(name: str):
    t = triggers_mod.get(get_conn(), name)
    if not t:
        raise HTTPException(404, "not found")
    return t


@app.delete("/triggers/{name}")
def triggers_delete(name: str):
    triggers_mod.delete(get_conn(), name)
    audit_mod.log_action(get_conn(), "trigger.delete", {"name": name})
    return {"ok": True}


@app.post("/triggers/{name}/toggle")
def triggers_toggle(name: str):
    t = triggers_mod.get(get_conn(), name)
    if not t:
        raise HTTPException(404, "not found")
    triggers_mod.set_enabled(get_conn(), name, not bool(t.get("enabled")))
    return {"ok": True, "enabled": not bool(t.get("enabled"))}


@app.post("/triggers/{name}/run")
def triggers_run(name: str):
    return triggers_mod.run_once(get_conn(), name)


@app.post("/triggers/author")
async def triggers_author(body: TriggerAuthor):
    """Plain English → trigger recipe via internal Gemini agent. Saves it."""
    import httpx
    c = get_conn()
    api_key = db.get_config(c, "gemini_api_key")
    if not api_key:
        raise HTTPException(400, "API key not set")
    try:
        spec = await triggers_mod.author_from_text(api_key, body.request)
    except ValueError as e:
        raise HTTPException(400, f"author failed: {e}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"LLM upstream error: {e.response.status_code}")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"LLM network error: {e}")
    try:
        tid = triggers_mod.create(c, spec["name"], spec["recipe"],
                                  interval_sec=int(spec.get("interval_sec", 300)),
                                  description=spec.get("description", ""))
    except ValueError as e:
        raise HTTPException(400, f"validate failed: {e}")
    audit_mod.log_action(c, "trigger.author",
                         {"name": spec["name"], "request": body.request})
    return {"id": tid, "spec": spec}
