"""FastAPI server — browser extension + CLI talk to this."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
from . import (
    db, classifier, monitor, blocker, skiplist, scheduler, interventions,
    stats as stats_mod, persistence,
    partners as partners_mod, penalties as penalties_mod,
    query as query_mod, importer as importer_mod, templates as templates_mod,
    dashboard as dashboard_mod,
    notifications as notifications_mod,
    whitelist as whitelist_mod,
    achievements as achievements_mod,
    points as points_mod,
    challenges as challenges_mod,
    leaderboard as leaderboard_mod,
    tracker as tracker_mod,
    context as context_mod,
    smart as smart_mod,
    reports as reports_mod,
    calendar as calendar_mod,
    habits as habits_mod,
    journal as journal_mod,
    commitments as commitments_mod,
    journeys as journeys_mod,
    mode as mode_mod,
    limits as limits_mod,
    sync as sync_mod,
    lockdown as lockdown_mod,
    sensitivity as sensitivity_mod,
    health as health_mod,
    digest as digest_mod,
    onboarding as onboarding_mod,
    export_formats as export_formats_mod,
    realtime as realtime_mod,
    focus_modes as focus_modes_mod,
    motivation as motivation_mod,
    nlp as nlp_mod,
    screenshots as screenshots_mod,
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


@app.get("/", response_class=HTMLResponse)
def dashboard_page():
    """Serve the single-page dashboard."""
    return HTMLResponse(content=dashboard_mod.get_dashboard_html())


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


# --- Health ---
@app.get("/health")
def health():
    return health_mod.check_health(get_conn())


# --- Notifications ---
class NotifyBody(BaseModel):
    title: str
    message: str
    channels: list = ["macos"]


@app.post("/notify")
async def notify(body: NotifyBody):
    return await notifications_mod.send_all(get_conn(), body.title, body.message, channels=body.channels)


# --- Whitelist ---
class WhitelistDomain(BaseModel):
    domain: str


@app.get("/whitelist")
def whitelist_list():
    c = get_conn()
    return {"enabled": whitelist_mod.is_whitelist_mode(c),
            "domains": whitelist_mod.get_whitelist(c)}


@app.post("/whitelist")
def whitelist_add(body: WhitelistDomain):
    whitelist_mod.add_to_whitelist(get_conn(), body.domain)
    return {"ok": True}


@app.delete("/whitelist/{domain}")
def whitelist_remove(domain: str):
    whitelist_mod.remove_from_whitelist(get_conn(), domain)
    return {"ok": True}


@app.post("/whitelist/enable")
def whitelist_enable():
    whitelist_mod.enable_whitelist_mode(get_conn())
    return {"ok": True}


@app.post("/whitelist/disable")
def whitelist_disable():
    whitelist_mod.disable_whitelist_mode(get_conn())
    return {"ok": True}


# --- Achievements ---
@app.get("/achievements")
def achievements_list():
    c = get_conn()
    return {"unlocked": achievements_mod.get_unlocked(c),
            "locked": achievements_mod.get_locked(c)}


@app.post("/achievements/check")
def achievements_check():
    return {"newly_unlocked": achievements_mod.check_achievements(get_conn())}


# --- Points ---
class PointsAward(BaseModel):
    action: str


@app.get("/points")
def points_get():
    c = get_conn()
    return {"total": points_mod.get_total_points(c), "level": points_mod.get_level(c)}


@app.get("/points/history")
def points_history(limit: int = 50):
    return points_mod.get_history(get_conn(), limit=limit)


@app.post("/points/award")
def points_award(body: PointsAward):
    return {"total": points_mod.award(get_conn(), body.action)}


# --- Challenges ---
class ChallengeCreate(BaseModel):
    name: str
    duration_hours: int
    rules: list = []


@app.post("/challenges")
def challenges_create(body: ChallengeCreate):
    cid = challenges_mod.create_challenge(get_conn(), body.name, body.duration_hours, body.rules)
    return {"id": cid}


@app.get("/challenges")
def challenges_list():
    return challenges_mod.get_active_challenges(get_conn())


@app.get("/challenges/{cid}")
def challenges_get(cid: int):
    c = challenges_mod.get_challenge(get_conn(), cid)
    if not c:
        raise HTTPException(status_code=404, detail="not found")
    return c


@app.post("/challenges/{cid}/complete")
def challenges_complete(cid: int):
    return {"ok": challenges_mod.complete_challenge(get_conn(), cid)}


@app.get("/challenges/stats")
def challenges_stats():
    return challenges_mod.challenge_stats(get_conn())


# --- Leaderboard ---
class LeaderboardScore(BaseModel):
    user: str
    date: str
    score: float


@app.get("/leaderboard")
def leaderboard_get(days: int = 7):
    return leaderboard_mod.get_leaderboard(get_conn(), days=days)


@app.post("/leaderboard")
def leaderboard_record(body: LeaderboardScore):
    leaderboard_mod.record_score(get_conn(), body.user, body.date, body.score)
    return {"ok": True}


@app.get("/leaderboard/{user}")
def leaderboard_user(user: str):
    return leaderboard_mod.get_user_stats(get_conn(), user)


# --- Tracker ---
class TrackerStart(BaseModel):
    project: str
    description: str = ""


@app.post("/tracker/start")
def tracker_start(body: TrackerStart):
    return {"id": tracker_mod.start_tracking(get_conn(), body.project, body.description)}


@app.post("/tracker/stop")
def tracker_stop():
    return tracker_mod.stop_tracking(get_conn()) or {}


@app.get("/tracker")
def tracker_active():
    return tracker_mod.get_active_tracking(get_conn()) or {}


@app.get("/tracker/projects")
def tracker_projects():
    return tracker_mod.list_projects(get_conn())


@app.get("/tracker/time")
def tracker_time(project: str = None, date: str = None):
    return tracker_mod.get_tracked_time(get_conn(), project=project, date_str=date)


# --- Context ---
class ContextSet(BaseModel):
    context: str


@app.get("/context")
def context_get():
    return {"context": context_mod.get_current_context(get_conn())}


@app.post("/context")
def context_set(body: ContextSet):
    context_mod.set_current_context(get_conn(), body.context)
    return {"ok": True}


@app.delete("/context")
def context_clear():
    context_mod.clear_context(get_conn())
    return {"ok": True}


# --- Smart ---
@app.get("/smart/duplicates")
def smart_duplicates():
    return smart_mod.find_duplicates(get_conn())


@app.get("/smart/conflicts")
def smart_conflicts():
    return smart_mod.find_conflicts(get_conn())


@app.get("/smart/suggestions")
async def smart_suggestions():
    c = get_conn()
    api_key = db.get_config(c, "gemini_api_key") or ""
    return await smart_mod.suggest_rules(c, api_key)


@app.get("/smart/coverage")
def smart_coverage():
    return smart_mod.coverage_report(get_conn())


@app.get("/smart/explain/{domain}")
async def smart_explain(domain: str):
    c = get_conn()
    api_key = db.get_config(c, "gemini_api_key") or ""
    return {"explanation": await smart_mod.explain_block(c, domain, api_key)}


# --- Reports ---
@app.get("/reports/daily")
async def reports_daily(date: str = None):
    c = get_conn()
    api_key = db.get_config(c, "gemini_api_key") or ""
    return {"report": await reports_mod.daily_report(c, api_key, date_str=date)}


@app.get("/reports/weekly")
async def reports_weekly():
    c = get_conn()
    api_key = db.get_config(c, "gemini_api_key") or ""
    return await reports_mod.weekly_insights(c, api_key)


@app.get("/reports/time-distribution")
def reports_time_distribution(date: str = None):
    return reports_mod.time_distribution(get_conn(), date_str=date)


@app.get("/reports/peak-hours")
def reports_peak_hours(days: int = 30):
    return {"peak_hours": reports_mod.peak_focus_hours(get_conn(), days=days)}


@app.get("/reports/triggers")
def reports_triggers():
    return reports_mod.distraction_triggers(get_conn())


# --- Calendar ---
class CalendarSync(BaseModel):
    ical_url: str


@app.post("/calendar/sync")
async def calendar_sync(body: CalendarSync):
    return {"count": await calendar_mod.sync_calendar(get_conn(), body.ical_url)}


@app.get("/calendar/events")
def calendar_events():
    return calendar_mod.get_cached_events(get_conn())


@app.get("/calendar/in-meeting")
def calendar_in_meeting():
    events = calendar_mod.get_cached_events(get_conn())
    return {"in_meeting": calendar_mod.is_in_meeting(events),
            "current_event": calendar_mod.get_current_event(events)}


# --- Habits ---
class HabitCreate(BaseModel):
    name: str
    frequency: str = "daily"
    target: int = 1


@app.post("/habits")
def habits_add(body: HabitCreate):
    return {"id": habits_mod.add_habit(get_conn(), body.name, body.frequency, body.target)}


@app.get("/habits")
def habits_list():
    return habits_mod.get_habits(get_conn())


@app.delete("/habits/{habit_id}")
def habits_remove(habit_id: int):
    habits_mod.delete_habit(get_conn(), habit_id)
    return {"ok": True}


@app.post("/habits/{habit_id}/log")
def habits_log(habit_id: int):
    return habits_mod.log_habit(get_conn(), habit_id)


@app.get("/habits/{habit_id}/stats")
def habits_stats(habit_id: int):
    return habits_mod.get_habit_stats(get_conn(), habit_id)


@app.get("/habits/today")
def habits_today():
    return habits_mod.get_todays_habits(get_conn())


# --- Journal ---
class JournalEntry(BaseModel):
    content: str
    mood: Optional[int] = None
    tags: list = []


@app.post("/journal")
def journal_add(body: JournalEntry):
    return {"id": journal_mod.add_entry(get_conn(), body.content, body.mood, body.tags)}


@app.get("/journal")
def journal_list(since: str = None, limit: int = 50):
    return journal_mod.get_entries(get_conn(), since=since, limit=limit)


@app.get("/journal/today")
def journal_today():
    return journal_mod.get_today_entry(get_conn()) or {}


@app.get("/journal/search")
def journal_search(q: str):
    return journal_mod.search_entries(get_conn(), q)


@app.get("/journal/mood")
def journal_mood(days: int = 30):
    return journal_mod.get_mood_trend(get_conn(), days=days)


@app.delete("/journal/{entry_id}")
def journal_delete(entry_id: int):
    journal_mod.delete_entry(get_conn(), entry_id)
    return {"ok": True}


# --- Commitments ---
class CommitmentCreate(BaseModel):
    text: str
    deadline: str
    stakes: str = ""


class CommitmentComplete(BaseModel):
    proof: Optional[str] = None


@app.post("/commitments")
def commitments_add(body: CommitmentCreate):
    return {"id": commitments_mod.create_commitment(get_conn(), body.text, body.deadline, body.stakes)}


@app.get("/commitments")
def commitments_list(status: str = "active"):
    return commitments_mod.get_commitments(get_conn(), status=status)


@app.post("/commitments/{cid}/complete")
def commitments_complete(cid: int, body: CommitmentComplete):
    commitments_mod.complete_commitment(get_conn(), cid, body.proof)
    return {"ok": True}


@app.get("/commitments/overdue")
def commitments_overdue():
    return commitments_mod.overdue_commitments(get_conn())


# --- Journeys ---
class JourneyCreate(BaseModel):
    name: str
    description: str = ""
    milestones: list = []


@app.post("/journeys")
def journeys_add(body: JourneyCreate):
    return {"id": journeys_mod.create_journey(get_conn(), body.name, body.description, body.milestones)}


@app.get("/journeys")
def journeys_list(active: bool = True):
    return journeys_mod.get_journeys(get_conn(), active=active)


@app.post("/journeys/{jid}/milestone/{index}")
def journeys_milestone(jid: int, index: int):
    journeys_mod.complete_milestone(get_conn(), jid, index)
    return {"ok": True}


@app.get("/journeys/{jid}/progress")
def journeys_progress(jid: int):
    p = journeys_mod.get_journey_progress(get_conn(), jid)
    if p is None:
        raise HTTPException(status_code=404, detail="not found")
    return p


@app.delete("/journeys/{jid}")
def journeys_delete(jid: int):
    journeys_mod.delete_journey(get_conn(), jid)
    return {"ok": True}


# --- Mode ---
class ModeSwitch(BaseModel):
    mode: str


@app.post("/mode/switch")
def mode_switch(body: ModeSwitch):
    return mode_mod.switch_mode(get_conn(), body.mode)


@app.get("/mode")
def mode_current():
    return {"mode": mode_mod.get_current_mode(get_conn())}


@app.get("/mode/list")
def mode_list():
    return mode_mod.list_modes()


# --- Limits ---
class LimitCreate(BaseModel):
    category: str
    period: str = "daily"
    max_seconds: int


@app.post("/limits")
def limits_add(body: LimitCreate):
    return {"id": limits_mod.set_limit(get_conn(), body.category, body.period, body.max_seconds)}


@app.get("/limits")
def limits_list():
    return limits_mod.get_limits(get_conn())


@app.delete("/limits/{limit_id}")
def limits_remove(limit_id: int):
    limits_mod.delete_limit(get_conn(), limit_id)
    return {"ok": True}


@app.get("/limits/status")
def limits_status():
    return limits_mod.get_all_limit_status(get_conn())


# --- Sync ---
@app.post("/sync/push")
async def sync_push():
    c = get_conn()
    return await sync_mod.push_to_sync(c, sync_mod.get_sync_url(c), sync_mod.get_device_id(c))


@app.post("/sync/pull")
async def sync_pull():
    c = get_conn()
    return await sync_mod.pull_from_sync(c, sync_mod.get_sync_url(c), sync_mod.get_device_id(c))


# --- Lockdown ---
class LockdownEnter(BaseModel):
    duration_minutes: int
    password_hash: Optional[str] = None


class LockdownExit(BaseModel):
    password: Optional[str] = None


@app.post("/lockdown/enter")
def lockdown_enter(body: LockdownEnter):
    return lockdown_mod.enter_lockdown(get_conn(), body.duration_minutes, body.password_hash)


@app.post("/lockdown/exit")
def lockdown_exit(body: LockdownExit):
    return {"ok": lockdown_mod.try_exit_lockdown(get_conn(), body.password)}


@app.get("/lockdown/status")
def lockdown_status():
    c = get_conn()
    return {"active": lockdown_mod.is_in_lockdown(c),
            "end_ts": lockdown_mod.get_lockdown_end(c)}


# --- Sensitivity ---
class SensitivitySet(BaseModel):
    level: str


@app.get("/sensitivity")
def sensitivity_get():
    c = get_conn()
    return {"level": sensitivity_mod.get_sensitivity(c),
            "config": sensitivity_mod.get_sensitivity_config(c)}


@app.post("/sensitivity")
def sensitivity_set(body: SensitivitySet):
    try:
        sensitivity_mod.set_sensitivity(get_conn(), body.level)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


# --- Digest ---
@app.get("/digest/daily")
async def digest_daily():
    c = get_conn()
    api_key = db.get_config(c, "gemini_api_key") or ""
    return {"digest": await digest_mod.generate_daily_digest(c, api_key)}


@app.get("/digest/weekly")
async def digest_weekly():
    c = get_conn()
    api_key = db.get_config(c, "gemini_api_key") or ""
    return {"digest": await digest_mod.generate_weekly_digest(c, api_key)}


# --- Onboarding ---
class OnboardingApply(BaseModel):
    persona: str


@app.get("/onboarding")
def onboarding_check():
    return {"first_run": onboarding_mod.is_first_run(get_conn()),
            "personas": onboarding_mod.list_personas()}


@app.post("/onboarding/apply")
def onboarding_apply(body: OnboardingApply):
    try:
        return onboarding_mod.create_persona_setup(get_conn(), body.persona)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Export formats ---
@app.get("/export/rules.csv")
def export_rules_csv():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(export_formats_mod.rules_to_csv(get_conn()), media_type="text/csv")


@app.get("/export/rules.md")
def export_rules_md():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(export_formats_mod.rules_to_markdown(get_conn()), media_type="text/markdown")


@app.get("/export/stats.csv")
def export_stats_csv(days: int = 30):
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(export_formats_mod.stats_to_csv(get_conn(), days=days), media_type="text/csv")


@app.get("/export/activity.csv")
def export_activity_csv(days: int = 7):
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(export_formats_mod.activity_to_csv(get_conn(), days=days), media_type="text/csv")


@app.get("/export/report.md")
def export_report_md():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(export_formats_mod.full_report_markdown(get_conn()), media_type="text/markdown")


@app.get("/export/report.html")
def export_report_html():
    return HTMLResponse(export_formats_mod.full_report_html(get_conn()))


# --- Real-time events (SSE) ---
@app.get("/events")
async def events():
    """Server-Sent Events stream for the live dashboard."""
    queue = realtime_mod.subscribe()
    return StreamingResponse(realtime_mod.event_stream(queue), media_type="text/event-stream")


# --- Focus modes ---
@app.get("/focus-modes")
def focus_modes_list():
    return focus_modes_mod.list_modes()


class FocusModeStart(BaseModel):
    mode: str


@app.post("/focus-modes/start")
def focus_modes_start(body: FocusModeStart):
    try:
        return focus_modes_mod.start_mode(get_conn(), body.mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/focus-modes/current")
def focus_modes_current():
    return focus_modes_mod.current_mode_state(get_conn()) or {}


# --- Motivation ---
@app.get("/motivation/quote")
def motivation_quote(moment: str = ""):
    quote, author = (motivation_mod.get_quote_for_moment(moment)
                     if moment else motivation_mod.get_random_quote())
    return {"quote": quote, "author": author}


@app.get("/motivation/affirmation")
def motivation_affirmation():
    return {"text": motivation_mod.daily_affirmation(get_conn())}


# --- Vision ---
class VisionStart(BaseModel):
    interval: int = 120


@app.post("/vision/start")
def vision_start(body: VisionStart):
    c = get_conn()
    api_key = db.get_config(c, "gemini_api_key") or ""
    screenshots_mod.start_vision_monitor(c, api_key, body.interval)
    return {"active": screenshots_mod.is_vision_active()}


@app.post("/vision/stop")
def vision_stop():
    screenshots_mod.stop_vision_monitor()
    return {"active": screenshots_mod.is_vision_active()}


@app.get("/vision/last")
def vision_last():
    return screenshots_mod.get_last_verdict()
