"""FastAPI server — browser extension + CLI talk to this."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from . import (
    db, classifier, monitor, blocker, skiplist, scheduler, interventions,
    stats as stats_mod, persistence,
    partners as partners_mod, penalties as penalties_mod,
    query as query_mod, importer as importer_mod, templates as templates_mod,
)
import asyncio

app = FastAPI(title="Sentinel")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
conn = None


def get_conn():
    global conn
    if conn is None:
        conn = db.connect()
    return conn


class ActivityReport(BaseModel):
    url: str = ""
    title: str = ""
    domain: str = ""


class RuleCreate(BaseModel):
    text: str


class ConfigSet(BaseModel):
    key: str
    value: str


@app.on_event("startup")
def startup():
    global conn
    conn = db.connect()
    monitor.start()
    persistence.start_watcher()


@app.post("/activity")
async def report_activity(report: ActivityReport):
    """Browser extension reports current URL."""
    monitor.set_browser_url(report.url)
    c = get_conn()
    api_key = db.get_config(c, "gemini_api_key")
    if not api_key or not report.domain:
        return {"verdict": "allow"}

    # Skip utility domains
    if skiplist.should_skip(report.domain):
        return {"verdict": "allow"}

    # Check if already seen
    seen = db.get_seen(c, report.domain)
    if seen == "none" or seen == "approved":
        return {"verdict": "allow"}

    # Check if already blocked
    if blocker.is_blocked_domain(report.domain):
        return {"verdict": "block"}

    # Classify if unseen
    if not seen:
        category = await classifier.classify_domain(api_key, report.domain)
        db.save_seen(c, report.domain, category)
        if category in ("streaming", "social", "adult", "gaming"):
            # Check rules
            rules = db.get_rules(c)
            if rules:
                verdict = await classifier.evaluate_rules(
                    api_key, report.title or "", report.domain, report.title or "", rules)
                if verdict == "block":
                    blocker.block_domain(report.domain)
                    db.log_activity(c, "", report.title, report.url, report.domain, "block")
                    return {"verdict": "block", "category": category}
            else:
                # No rules — auto-block known bad categories
                if category in ("adult",):
                    blocker.block_domain(report.domain)
                    return {"verdict": "block", "category": category}
                return {"verdict": "warn", "category": category}
        return {"verdict": "allow"}

    # Already categorized as bad
    if seen in ("streaming", "social", "adult", "gaming"):
        rules = db.get_rules(c)
        if rules:
            verdict = await classifier.evaluate_rules(
                api_key, "", report.domain, report.title or "", rules)
            return {"verdict": verdict, "category": seen}
    return {"verdict": "allow"}


@app.post("/rules")
async def create_rule(rule: RuleCreate):
    """Create a new rule from natural language."""
    c = get_conn()
    api_key = db.get_config(c, "gemini_api_key")
    parsed = {}
    if api_key:
        parsed = await classifier.parse_rule(api_key, rule.text)
    rule_id = db.add_rule(c, rule.text, parsed)
    return {"id": rule_id, "text": rule.text, "parsed": parsed}


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


@app.get("/status")
def status():
    c = get_conn()
    return {
        "current_activity": monitor.get_current(),
        "active_rules": db.get_rules(c),
        "blocked": blocker.get_blocked(),
    }


@app.get("/stats")
def stats():
    c = get_conn()
    activities = db.get_activities(c, limit=500)
    blocked = sum(1 for a in activities if a.get("verdict") == "block")
    return {"total_activities": len(activities), "blocked_count": blocked}


@app.post("/config")
def set_config(cfg: ConfigSet):
    db.set_config(get_conn(), cfg.key, cfg.value)
    return {"ok": True}


@app.get("/config/{key}")
def get_config(key: str):
    return {"value": db.get_config(get_conn(), key)}


@app.post("/block/domain/{domain}")
def manual_block_domain(domain: str):
    blocker.block_domain(domain)
    return {"ok": True}


@app.delete("/block/domain/{domain}")
def manual_unblock_domain(domain: str):
    blocker.unblock_domain(domain)
    return {"ok": True}


# --- Pomodoro ---
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


# --- Focus sessions ---
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
    ok = scheduler.end_focus_session(get_conn(), session_id, force=force)
    return {"ok": ok}


# --- Interventions ---
class InterventionCreate(BaseModel):
    kind: str
    context: dict = {}


class InterventionSubmit(BaseModel):
    response: str


class InterventionNegotiate(BaseModel):
    message: str


@app.post("/intervention")
def intervention_create(body: InterventionCreate):
    try:
        return interventions.create_intervention(get_conn(), body.kind, body.context)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/intervention/{iid}")
def intervention_get(iid: int):
    iv = interventions.get_intervention(get_conn(), iid)
    if not iv:
        raise HTTPException(status_code=404, detail="not found")
    return iv


@app.post("/intervention/{iid}/submit")
def intervention_submit(iid: int, body: InterventionSubmit):
    return interventions.submit_intervention(get_conn(), iid, body.response)


@app.post("/intervention/{iid}/negotiate")
async def intervention_negotiate(iid: int, body: InterventionNegotiate):
    c = get_conn()
    api_key = db.get_config(c, "gemini_api_key") or ""
    return await interventions.ai_negotiate(c, iid, body.message, api_key)


# --- Stats ---
@app.get("/stats/score")
def stats_score():
    return {"score": stats_mod.calculate_score(get_conn())}


@app.get("/stats/breakdown")
def stats_breakdown():
    return stats_mod.get_daily_breakdown(get_conn())


@app.get("/stats/top-distractions")
def stats_top_distractions(days: int = 7):
    return stats_mod.get_top_distractions(get_conn(), days=days)


@app.get("/stats/week")
def stats_week():
    return stats_mod.get_week_summary(get_conn())


@app.get("/stats/month")
def stats_month():
    return stats_mod.get_month_summary(get_conn())


# --- Goals ---
class GoalCreate(BaseModel):
    name: str
    target_type: str
    target_value: int
    category: Optional[str] = None


@app.post("/goals")
def goals_add(body: GoalCreate):
    gid = stats_mod.add_goal(get_conn(), body.name, body.target_type, body.target_value, body.category)
    return {"id": gid}


@app.get("/goals")
def goals_list():
    return stats_mod.get_goals(get_conn())


@app.delete("/goals/{goal_id}")
def goals_remove(goal_id: int):
    stats_mod.delete_goal(get_conn(), goal_id)
    return {"ok": True}


@app.get("/goals/{goal_id}/progress")
def goals_progress(goal_id: int):
    p = stats_mod.check_goal_progress(get_conn(), goal_id)
    if p is None:
        raise HTTPException(status_code=404, detail="goal not found")
    return p


# --- Activity decision (browser extension) ---
class ActivityDecision(BaseModel):
    url: str
    decision: str


@app.post("/activity/decision")
def activity_decision(body: ActivityDecision):
    c = get_conn()
    from urllib.parse import urlparse
    domain = urlparse(body.url).netloc or ""
    db.log_activity(c, "", "", body.url, domain, verdict=f"decision:{body.decision}")
    return {"ok": True}


# --- Partners ---
class PartnerCreate(BaseModel):
    name: str
    contact: str
    method: str = "webhook"


@app.post("/partners")
def partners_add(body: PartnerCreate):
    pid = partners_mod.add_partner(get_conn(), body.name, body.contact, body.method)
    return {"id": pid}


@app.get("/partners")
def partners_list():
    return partners_mod.get_partners(get_conn())


@app.delete("/partners/{partner_id}")
def partners_remove(partner_id: int):
    partners_mod.delete_partner(get_conn(), partner_id)
    return {"ok": True}


# --- Penalties ---
class PenaltyCreate(BaseModel):
    rule_id: int
    amount: float


@app.post("/penalties")
def penalties_record(body: PenaltyCreate):
    pid = penalties_mod.record_violation(get_conn(), body.rule_id, body.amount)
    return {"id": pid}


@app.get("/penalties")
def penalties_list():
    return penalties_mod.get_pending_penalties(get_conn())


@app.get("/penalties/total")
def penalties_total():
    return {"owed": penalties_mod.total_owed(get_conn()),
            "paid": penalties_mod.total_paid(get_conn())}


@app.post("/penalties/{penalty_id}/paid")
def penalties_mark_paid(penalty_id: int):
    penalties_mod.mark_penalty_paid(get_conn(), penalty_id)
    return {"ok": True}


# --- Ask (natural language) ---
class AskBody(BaseModel):
    question: str


@app.post("/ask")
async def ask_question(body: AskBody):
    c = get_conn()
    api_key = db.get_config(c, "gemini_api_key") or ""
    answer = await query_mod.ask(c, body.question, api_key)
    return {"answer": answer}


# --- Import/export ---
@app.get("/export")
def export_data():
    return importer_mod.export_all(get_conn())


class ImportBody(BaseModel):
    data: dict


@app.post("/import")
def import_data(body: ImportBody):
    return importer_mod.import_all(get_conn(), body.data)


# --- Templates ---
@app.get("/templates")
def templates_list():
    return templates_mod.list_templates()


@app.post("/templates/{name}/apply")
def templates_apply(name: str):
    try:
        ids = templates_mod.apply_template(get_conn(), name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"rule_ids": ids}
