"""CLI interface — sentinel add/status/stats/config."""
import click, httpx, json, sys

API = "http://localhost:9849"


def _post(path, **kwargs):
    try:
        r = httpx.post(f"{API}{path}", json=kwargs, timeout=10)
        return r.json()
    except httpx.ConnectError:
        click.echo("Error: Sentinel server not running. Start with: sentinel serve")
        sys.exit(1)


def _get(path):
    try:
        r = httpx.get(f"{API}{path}", timeout=10)
        return r.json()
    except httpx.ConnectError:
        click.echo("Error: Sentinel server not running. Start with: sentinel serve")
        sys.exit(1)


def _delete(path):
    try:
        r = httpx.delete(f"{API}{path}", timeout=10)
        return r.json()
    except httpx.ConnectError:
        click.echo("Error: Sentinel server not running. Start with: sentinel serve")
        sys.exit(1)


@click.group()
def cli():
    """Sentinel — AI-native accountability app."""
    pass


@cli.command()
@click.argument("text")
def add(text):
    """Add a blocking rule in natural language."""
    result = _post("/rules", text=text)
    click.echo(f"Rule #{result['id']} created: {text}")
    if result.get("parsed"):
        click.echo(f"  Parsed: {json.dumps(result['parsed'], indent=2)}")


@cli.command()
def rules():
    """List all rules."""
    data = _get("/rules")
    if not data:
        click.echo("No rules yet. Add one: sentinel add \"Block YouTube during work\"")
        return
    for r in data:
        status = "ON" if r["active"] else "OFF"
        click.echo(f"  [{status}] #{r['id']}: {r['text']}")


@cli.command()
def status():
    """Show current activity and active blocks."""
    data = _get("/status")
    act = data["current_activity"]
    click.echo(f"App:    {act.get('app', 'N/A')}")
    click.echo(f"Title:  {act.get('title', 'N/A')}")
    click.echo(f"URL:    {act.get('url', 'N/A')}")
    click.echo(f"Domain: {act.get('domain', 'N/A')}")
    click.echo()
    blocked = data["blocked"]
    if blocked["domains"] or blocked["apps"]:
        click.echo("Blocked domains: " + ", ".join(blocked["domains"]) if blocked["domains"] else "")
        click.echo("Blocked apps:    " + ", ".join(blocked["apps"]) if blocked["apps"] else "")
    else:
        click.echo("No active blocks.")
    click.echo()
    rules = data["active_rules"]
    click.echo(f"{len(rules)} active rule(s).")


@cli.command()
def stats():
    """Show productivity stats."""
    data = _get("/stats")
    click.echo(f"Activities logged: {data['total_activities']}")
    click.echo(f"Times blocked:     {data['blocked_count']}")


@cli.command()
@click.option("--api-key", help="Gemini API key")
def config(api_key):
    """Configure Sentinel."""
    if api_key:
        _post("/config", key="gemini_api_key", value=api_key)
        click.echo("API key saved.")
    else:
        key = _get("/config/gemini_api_key")
        if key.get("value"):
            click.echo(f"API key: {key['value'][:8]}...")
        else:
            click.echo("No API key set. Run: sentinel config --api-key YOUR_KEY")


@cli.command()
@click.argument("rule_id", type=int)
def remove(rule_id):
    """Remove a rule."""
    _delete(f"/rules/{rule_id}")
    click.echo(f"Rule #{rule_id} removed.")


@cli.command()
@click.argument("rule_id", type=int)
def toggle(rule_id):
    """Toggle a rule on/off."""
    _post(f"/rules/{rule_id}/toggle")
    click.echo(f"Rule #{rule_id} toggled.")


@cli.command()
@click.argument("domain")
def block(domain):
    """Manually block a domain."""
    _post(f"/block/domain/{domain}")
    click.echo(f"Blocked: {domain}")


@cli.command()
@click.argument("domain")
def unblock(domain):
    """Manually unblock a domain."""
    _delete(f"/block/domain/{domain}")
    click.echo(f"Unblocked: {domain}")


@cli.command()
@click.option("--port", default=9849, help="Port number")
def serve(port):
    """Start the Sentinel server."""
    import uvicorn
    click.echo(f"Starting Sentinel on port {port}...")
    uvicorn.run("sentinel.server:app", host="127.0.0.1", port=port, log_level="info")


# --- Pomodoro ---
@cli.group()
def pomodoro():
    """Pomodoro timer commands."""
    pass


@pomodoro.command("start")
@click.option("--work", default=25, help="Work minutes")
@click.option("--break", "break_", default=5, help="Break minutes")
@click.option("--cycles", default=4, help="Number of cycles")
def pomodoro_start(work, break_, cycles):
    """Start a pomodoro session."""
    r = _post("/pomodoro/start", work_minutes=work, break_minutes=break_, cycles=cycles)
    click.echo(f"Pomodoro #{r.get('id')} started: {work}m work / {break_}m break x {cycles}")


@pomodoro.command("status")
def pomodoro_status():
    """Show current pomodoro state."""
    r = _get("/pomodoro")
    if not r:
        click.echo("No active pomodoro.")
        return
    click.echo(f"State: {r.get('state')} | cycle {r.get('cycle')} | {r.get('seconds_remaining')}s remaining")


@pomodoro.command("stop")
def pomodoro_stop():
    """Stop the current pomodoro."""
    _delete("/pomodoro")
    click.echo("Pomodoro stopped.")


# --- Focus ---
@cli.group()
def focus():
    """Focus session commands."""
    pass


@focus.command("start")
@click.option("--minutes", default=60, help="Duration in minutes")
@click.option("--locked", is_flag=True, help="Cannot cancel until done")
def focus_start(minutes, locked):
    """Start a focus session."""
    r = _post("/focus/start", duration_minutes=minutes, locked=locked)
    lock_str = " (LOCKED)" if locked else ""
    click.echo(f"Focus session #{r.get('id')} started: {minutes}m{lock_str}")


@focus.command("status")
def focus_status():
    """Show current focus session."""
    r = _get("/focus")
    if not r:
        click.echo("No active focus session.")
        return
    locked = " (LOCKED)" if r.get("locked") else ""
    click.echo(f"Focus #{r.get('id')}{locked}: {r.get('seconds_remaining')}s remaining")


# --- Goals ---
@cli.group()
def goal():
    """Goal commands."""
    pass


@goal.command("add")
@click.argument("name")
@click.option("--type", "target_type", required=True,
              help="Target type: max_seconds, min_seconds, max_visits, zero")
@click.option("--value", type=int, required=True, help="Target value")
@click.option("--category", default=None, help="Category filter")
def goal_add(name, target_type, value, category):
    """Add a goal."""
    r = _post("/goals", name=name, target_type=target_type, target_value=value, category=category)
    click.echo(f"Goal #{r.get('id')} created: {name}")


@goal.command("list")
def goal_list():
    """List all goals."""
    data = _get("/goals")
    if not data:
        click.echo("No goals yet.")
        return
    for g in data:
        cat = f" [{g.get('category')}]" if g.get("category") else ""
        click.echo(f"  #{g['id']}: {g['name']} — {g['target_type']}={g['target_value']}{cat}")


@goal.command("remove")
@click.argument("goal_id", type=int)
def goal_remove(goal_id):
    """Remove a goal."""
    _delete(f"/goals/{goal_id}")
    click.echo(f"Goal #{goal_id} removed.")


# --- Stats ---
@cli.command()
def score():
    """Show today's productivity score."""
    r = _get("/stats/score")
    click.echo(f"Today's score: {r.get('score')}/100")


@cli.command()
def top():
    """Show top distractions."""
    data = _get("/stats/top-distractions")
    if not data:
        click.echo("No distractions logged.")
        return
    click.echo("Top distractions (last 7 days):")
    for d in data:
        mins = round((d.get("seconds") or 0) / 60, 1)
        click.echo(f"  {d['domain']}: {mins}m")


@cli.command()
def week():
    """Show weekly summary."""
    r = _get("/stats/week")
    click.echo(f"Past {r.get('days')} days:")
    click.echo(f"  Avg score:     {r.get('avg_score')}/100")
    click.echo(f"  Productive:    {round((r.get('productive') or 0) / 3600, 1)}h")
    click.echo(f"  Distracting:   {round((r.get('distracting') or 0) / 3600, 1)}h")


# --- Intervention test ---
@cli.group()
def intervention():
    """Intervention commands."""
    pass


@intervention.command("test")
@click.option("--kind", default="typing", help="Intervention kind")
def intervention_test(kind):
    """Test an intervention interactively."""
    r = _post("/intervention", kind=kind, context={})
    if "id" not in r:
        click.echo(f"Error: {r}")
        return
    iid = r["id"]
    click.echo(r.get("prompt", ""))
    if kind in ("typing", "math"):
        response = click.prompt("Your answer")
        result = _post(f"/intervention/{iid}/submit", response=response)
        click.echo(f"Result: {'PASSED' if result.get('passed') else 'FAILED'} — {result.get('feedback')}")
    elif kind in ("countdown", "wait", "breathing"):
        click.echo(f"(deadline at {r.get('deadline')})")
        click.pause("Press any key when done...")
        result = _post(f"/intervention/{iid}/submit", response="done")
        click.echo(f"Result: {'PASSED' if result.get('passed') else 'FAILED'} — {result.get('feedback')}")
    else:
        click.echo(f"Interactive test not implemented for kind={kind}")


# --- Partners ---
@cli.group()
def partner():
    """Accountability partner commands."""
    pass


@partner.command("add")
@click.argument("name")
@click.argument("contact")
@click.option("--method", default="webhook", help="webhook|email|sms")
def partner_add(name, contact, method):
    """Add an accountability partner."""
    r = _post("/partners", name=name, contact=contact, method=method)
    click.echo(f"Partner #{r.get('id')} added: {name}")


@partner.command("list")
def partner_list():
    """List all partners."""
    data = _get("/partners")
    if not data:
        click.echo("No partners yet.")
        return
    for p in data:
        click.echo(f"  #{p['id']}: {p['name']} [{p['method']}] -> {p['contact']}")


@partner.command("remove")
@click.argument("partner_id", type=int)
def partner_remove(partner_id):
    """Remove a partner."""
    _delete(f"/partners/{partner_id}")
    click.echo(f"Partner #{partner_id} removed.")


# --- Penalties ---
@cli.group()
def penalty():
    """Financial penalty commands."""
    pass


@penalty.command("list")
def penalty_list():
    """List pending penalties."""
    data = _get("/penalties")
    if not data:
        click.echo("No pending penalties.")
        return
    for p in data:
        click.echo(f"  #{p['id']}: rule {p['rule_id']} ${p['amount']:.2f}")


@penalty.command("total")
def penalty_total():
    """Show total owed."""
    r = _get("/penalties/total")
    click.echo(f"Owed: ${r.get('owed', 0):.2f}")
    click.echo(f"Paid: ${r.get('paid', 0):.2f}")


# --- Ask ---
@cli.command()
@click.argument("question", nargs=-1, required=True)
def ask(question):
    """Ask Sentinel a question about your data."""
    q = " ".join(question)
    r = _post("/ask", question=q)
    click.echo(r.get("answer", ""))


# --- Export/import ---
@cli.command("export")
def export_cmd():
    """Export rules/goals/partners/config as JSON."""
    r = _get("/export")
    click.echo(json.dumps(r, indent=2))


@cli.command("import")
@click.argument("path", type=click.Path(exists=True))
def import_cmd(path):
    """Import rules/goals/partners/config from JSON file."""
    with open(path) as f:
        data = json.load(f)
    r = _post("/import", data=data)
    click.echo(f"Imported: {r}")


# --- Templates ---
@cli.group()
def template():
    """Predefined rule templates."""
    pass


@template.command("list")
def template_list():
    """List available templates."""
    data = _get("/templates")
    for t in data:
        click.echo(f"  {t['key']}: {t['name']} ({t['rule_count']} rules)")
        click.echo(f"      {t['description']}")


@template.command("apply")
@click.argument("name")
def template_apply(name):
    """Apply a template to create its rules."""
    r = _post(f"/templates/{name}/apply")
    if "rule_ids" in r:
        click.echo(f"Applied {name}: created rules {r['rule_ids']}")
    else:
        click.echo(f"Error: {r}")


# --- Health ---
@cli.command()
def health():
    """Show system health check."""
    r = _get("/health")
    click.echo(f"API key set:       {r.get('api_key_set')}")
    click.echo(f"Database:          {r.get('database_healthy')}")
    click.echo(f"/etc/hosts:        {r.get('hosts_writable')}")
    click.echo(f"Daemon:            {r.get('daemon_running')}")
    click.echo(f"Extension:         {r.get('browser_extension_connected')}")
    click.echo(f"Rules:             {r.get('rules_count')}")
    for issue in r.get("issues", []):
        click.echo(f"  ! {issue}")


# --- Notify ---
@cli.command()
@click.argument("title")
@click.argument("message")
@click.option("--channel", "channels", multiple=True, default=["macos"])
def notify(title, message, channels):
    """Send a notification."""
    r = _post("/notify", title=title, message=message, channels=list(channels))
    click.echo(f"Sent: {r}")


# --- Whitelist ---
@cli.group()
def whitelist():
    """Whitelist mode."""
    pass


@whitelist.command("list")
def whitelist_list():
    """List whitelisted domains."""
    r = _get("/whitelist")
    click.echo(f"Mode: {'ON' if r.get('enabled') else 'OFF'}")
    for d in r.get("domains", []):
        click.echo(f"  {d}")


@whitelist.command("add")
@click.argument("domain")
def whitelist_add(domain):
    """Add domain to whitelist."""
    _post("/whitelist", domain=domain)
    click.echo(f"Added: {domain}")


@whitelist.command("remove")
@click.argument("domain")
def whitelist_remove(domain):
    """Remove domain from whitelist."""
    _delete(f"/whitelist/{domain}")
    click.echo(f"Removed: {domain}")


@whitelist.command("enable")
def whitelist_enable():
    """Enable whitelist mode."""
    _post("/whitelist/enable")
    click.echo("Whitelist mode enabled.")


@whitelist.command("disable")
def whitelist_disable():
    """Disable whitelist mode."""
    _post("/whitelist/disable")
    click.echo("Whitelist mode disabled.")


# --- Achievements ---
@cli.group()
def achievement():
    """Achievement commands."""
    pass


@achievement.command("list")
def achievement_list():
    """List achievements."""
    r = _get("/achievements")
    click.echo("Unlocked:")
    for a in r.get("unlocked", []):
        click.echo(f"  [x] {a['name']} — {a['desc']}")
    click.echo("Locked:")
    for a in r.get("locked", []):
        click.echo(f"  [ ] {a['name']} — {a['desc']}")


@achievement.command("check")
def achievement_check():
    """Check for newly unlocked achievements."""
    r = _post("/achievements/check")
    newly = r.get("newly_unlocked", [])
    if newly:
        click.echo(f"Newly unlocked: {newly}")
    else:
        click.echo("No new achievements.")


# --- Points ---
@cli.group()
def points():
    """Points and leveling."""
    pass


@points.command("total")
def points_total():
    """Show total points and level."""
    r = _get("/points")
    lvl = r.get("level", {})
    click.echo(f"Total: {r.get('total')} XP")
    click.echo(f"Level: {lvl.get('level')} ({lvl.get('progress_percent')}%)")


@points.command("history")
def points_history():
    """Show points history."""
    data = _get("/points/history")
    for p in data:
        click.echo(f"  {p.get('reason')}: +{p.get('amount')}")


@points.command("award")
@click.argument("action")
def points_award(action):
    """Award points for an action."""
    r = _post("/points/award", action=action)
    click.echo(f"Total: {r.get('total')}")


# --- Challenges ---
@cli.group()
def challenge():
    """Challenges."""
    pass


@challenge.command("create")
@click.argument("name")
@click.option("--hours", type=int, required=True)
def challenge_create(name, hours):
    """Create a challenge."""
    r = _post("/challenges", name=name, duration_hours=hours, rules=[])
    click.echo(f"Challenge #{r.get('id')} created.")


@challenge.command("list")
def challenge_list():
    """List active challenges."""
    for c in _get("/challenges"):
        click.echo(f"  #{c['id']}: {c['name']} ({c.get('seconds_remaining', 0) // 60}min left)")


@challenge.command("complete")
@click.argument("challenge_id", type=int)
def challenge_complete(challenge_id):
    """Complete a challenge."""
    r = _post(f"/challenges/{challenge_id}/complete")
    click.echo(f"Completed: {r.get('ok')}")


# --- Leaderboard ---
@cli.group()
def leaderboard():
    """Leaderboard."""
    pass


@leaderboard.command("show")
def leaderboard_show():
    """Show leaderboard."""
    for row in _get("/leaderboard"):
        click.echo(f"  {row['user']}: {row['avg_score']} ({row['days_tracked']}d)")


@leaderboard.command("record")
@click.argument("user")
@click.argument("date")
@click.argument("score", type=float)
def leaderboard_record(user, date, score):
    """Record a score."""
    _post("/leaderboard", user=user, date=date, score=score)
    click.echo("Recorded.")


# --- Tracker ---
@cli.group()
def tracker():
    """Time tracker."""
    pass


@tracker.command("start")
@click.argument("project")
@click.option("--description", default="")
def tracker_start(project, description):
    """Start tracking time."""
    r = _post("/tracker/start", project=project, description=description)
    click.echo(f"Tracking #{r.get('id')}: {project}")


@tracker.command("stop")
def tracker_stop():
    """Stop tracking time."""
    r = _post("/tracker/stop")
    click.echo(f"Stopped: {r}")


@tracker.command("status")
def tracker_status():
    """Show active tracking."""
    r = _get("/tracker")
    if not r:
        click.echo("Not tracking.")
        return
    click.echo(f"Tracking: {r.get('project')} — {r.get('description') or ''}")


@tracker.command("projects")
def tracker_projects():
    """List projects."""
    for p in _get("/tracker/projects"):
        mins = round((p["total_seconds"] or 0) / 60, 1)
        click.echo(f"  {p['project']}: {p['sessions']} sessions, {mins}m")


# --- Context ---
@cli.group()
def context():
    """Current context."""
    pass


@context.command("set")
@click.argument("text")
def context_set(text):
    """Set current context."""
    _post("/context", context=text)
    click.echo(f"Context: {text}")


@context.command("get")
def context_get():
    """Get current context."""
    r = _get("/context")
    click.echo(r.get("context") or "(none)")


@context.command("clear")
def context_clear():
    """Clear current context."""
    _delete("/context")
    click.echo("Cleared.")


# --- Smart ---
@cli.group()
def smart():
    """Smart rule analysis."""
    pass


@smart.command("duplicates")
def smart_duplicates():
    """Find duplicate rules."""
    data = _get("/smart/duplicates")
    if not data:
        click.echo("No duplicates.")
        return
    for d in data:
        click.echo(f"  {d}")


@smart.command("conflicts")
def smart_conflicts():
    """Find conflicting rules."""
    data = _get("/smart/conflicts")
    if not data:
        click.echo("No conflicts.")
        return
    for c in data:
        click.echo(f"  {c['domain']}: {len(c['rules'])} rules")


@smart.command("suggestions")
def smart_suggestions():
    """LLM-suggested new rules."""
    for s in _get("/smart/suggestions"):
        click.echo(f"  - {s}")


@smart.command("coverage")
def smart_coverage():
    """Show rule coverage."""
    r = _get("/smart/coverage")
    click.echo(f"Coverage: {r.get('coverage_percent')}%")


@smart.command("explain")
@click.argument("domain")
def smart_explain(domain):
    """Explain why a domain would be blocked."""
    r = _get(f"/smart/explain/{domain}")
    click.echo(r.get("explanation", ""))


# --- Reports ---
@cli.group()
def report():
    """Reports and insights."""
    pass


@report.command("daily")
def report_daily():
    """Daily report."""
    r = _get("/reports/daily")
    click.echo(r.get("report", ""))


@report.command("weekly")
def report_weekly():
    """Weekly insights."""
    r = _get("/reports/weekly")
    click.echo(f"Summary: {r.get('summary')}")
    for p in r.get("patterns", []):
        click.echo(f"  pattern: {p}")
    for rec in r.get("recommendations", []):
        click.echo(f"  rec: {rec}")


@report.command("time-distribution")
def report_time_distribution():
    """Hourly time distribution."""
    r = _get("/reports/time-distribution")
    for h, s in sorted(r.items(), key=lambda x: int(x[0])):
        click.echo(f"  {h}h: {round((s or 0)/60, 1)}m")


@report.command("peak-hours")
def report_peak_hours():
    """Peak productive hours."""
    r = _get("/reports/peak-hours")
    click.echo(f"Peak hours: {r.get('peak_hours')}")


@report.command("triggers")
def report_triggers():
    """Distraction triggers."""
    for t in _get("/reports/triggers"):
        click.echo(f"  {t['trigger']} -> {t['distraction']} ({t['count']})")


# --- Calendar ---
@cli.group()
def calendar():
    """Calendar integration."""
    pass


@calendar.command("sync")
@click.argument("ical_url")
def calendar_sync(ical_url):
    """Sync calendar from iCal URL."""
    r = _post("/calendar/sync", ical_url=ical_url)
    click.echo(f"Synced {r.get('count')} events.")


@calendar.command("events")
def calendar_events():
    """List cached events."""
    for e in _get("/calendar/events"):
        click.echo(f"  {e.get('title')}")


@calendar.command("in-meeting")
def calendar_in_meeting():
    """Check if in meeting."""
    r = _get("/calendar/in-meeting")
    click.echo(f"In meeting: {r.get('in_meeting')}")


# --- Habits ---
@cli.group()
def habit():
    """Habit tracking."""
    pass


@habit.command("add")
@click.argument("name")
@click.option("--frequency", default="daily")
@click.option("--target", type=int, default=1)
def habit_add(name, frequency, target):
    """Add a habit."""
    r = _post("/habits", name=name, frequency=frequency, target=target)
    click.echo(f"Habit #{r.get('id')} added: {name}")


@habit.command("list")
def habit_list():
    """List all habits."""
    for h in _get("/habits"):
        click.echo(f"  #{h['id']}: {h['name']} ({h.get('frequency', 'daily')})")


@habit.command("log")
@click.argument("habit_id", type=int)
def habit_log(habit_id):
    """Log a habit for today."""
    r = _post(f"/habits/{habit_id}/log")
    click.echo(f"Logged: {r}")


@habit.command("stats")
@click.argument("habit_id", type=int)
def habit_stats(habit_id):
    """Show habit stats."""
    r = _get(f"/habits/{habit_id}/stats")
    click.echo(f"Current streak: {r.get('current_streak')}")
    click.echo(f"Longest streak: {r.get('longest_streak')}")
    click.echo(f"Completion:     {r.get('completion_rate')}%")


@habit.command("today")
def habit_today():
    """Show today's habits."""
    for h in _get("/habits/today"):
        status = "[x]" if h.get("done") else "[ ]"
        click.echo(f"  {status} {h['name']}")


@habit.command("remove")
@click.argument("habit_id", type=int)
def habit_remove(habit_id):
    """Remove a habit."""
    _delete(f"/habits/{habit_id}")
    click.echo(f"Removed habit #{habit_id}")


# --- Journal ---
@cli.group()
def journal():
    """Reflection journal."""
    pass


@journal.command("add")
@click.argument("content")
@click.option("--mood", type=int, default=None)
@click.option("--tag", "tags", multiple=True)
def journal_add(content, mood, tags):
    """Add a journal entry."""
    r = _post("/journal", content=content, mood=mood, tags=list(tags))
    click.echo(f"Entry #{r.get('id')} added.")


@journal.command("list")
def journal_list():
    """List journal entries."""
    for e in _get("/journal"):
        click.echo(f"  #{e['id']} [{e['date']}]: {e['content'][:60]}")


@journal.command("today")
def journal_today():
    """Show today's entry."""
    r = _get("/journal/today")
    if not r:
        click.echo("(none)")
        return
    click.echo(r.get("content", ""))


@journal.command("search")
@click.argument("query")
def journal_search(query):
    """Search journal entries."""
    for e in _get(f"/journal/search?q={query}"):
        click.echo(f"  #{e['id']}: {e['content'][:60]}")


@journal.command("mood")
def journal_mood():
    """Show mood trend."""
    for m in _get("/journal/mood"):
        click.echo(f"  {m['date']}: {m['avg_mood']}")


# --- Commitments ---
@cli.group()
def commitment():
    """Social commitments."""
    pass


@commitment.command("add")
@click.argument("text")
@click.option("--deadline", required=True)
@click.option("--stakes", default="")
def commitment_add(text, deadline, stakes):
    """Add a commitment."""
    r = _post("/commitments", text=text, deadline=deadline, stakes=stakes)
    click.echo(f"Commitment #{r.get('id')} added.")


@commitment.command("list")
def commitment_list():
    """List active commitments."""
    for c in _get("/commitments"):
        click.echo(f"  #{c['id']}: {c['text']} (by {c['deadline']})")


@commitment.command("complete")
@click.argument("cid", type=int)
@click.option("--proof", default=None)
def commitment_complete(cid, proof):
    """Mark commitment complete."""
    _post(f"/commitments/{cid}/complete", proof=proof)
    click.echo(f"Completed #{cid}")


@commitment.command("overdue")
def commitment_overdue():
    """Show overdue commitments."""
    for c in _get("/commitments/overdue"):
        click.echo(f"  #{c['id']}: {c['text']} (was due {c['deadline']})")


# --- Journeys ---
@cli.group()
def journey():
    """Long-term journeys."""
    pass


@journey.command("create")
@click.argument("name")
@click.option("--description", default="")
@click.option("--milestone", "milestones", multiple=True)
def journey_create(name, description, milestones):
    """Create a journey."""
    r = _post("/journeys", name=name, description=description, milestones=list(milestones))
    click.echo(f"Journey #{r.get('id')} created.")


@journey.command("list")
def journey_list():
    """List active journeys."""
    for j in _get("/journeys"):
        click.echo(f"  #{j['id']}: {j['name']} ({len(j['completed_indices'])}/{len(j['milestones'])})")


@journey.command("milestone")
@click.argument("jid", type=int)
@click.argument("index", type=int)
def journey_milestone(jid, index):
    """Complete a milestone."""
    _post(f"/journeys/{jid}/milestone/{index}")
    click.echo(f"Milestone {index} completed.")


@journey.command("progress")
@click.argument("jid", type=int)
def journey_progress(jid):
    """Show journey progress."""
    r = _get(f"/journeys/{jid}/progress")
    click.echo(f"{r.get('name')}: {r.get('completed')}/{r.get('total')} ({r.get('percent')}%)")


# --- Mode ---
@cli.group()
def mode():
    """Mode switching."""
    pass


@mode.command("switch")
@click.argument("name")
def mode_switch(name):
    """Switch to a mode."""
    r = _post("/mode/switch", mode=name)
    click.echo(f"Mode: {r}")


@mode.command("current")
def mode_current():
    """Show current mode."""
    r = _get("/mode")
    click.echo(r.get("mode"))


@mode.command("list")
def mode_list():
    """List available modes."""
    for m in _get("/mode/list"):
        click.echo(f"  {m['name']}: blocks {m['block_categories']}")


# --- Limits ---
@cli.group()
def limit():
    """Time limits per category."""
    pass


@limit.command("add")
@click.argument("category")
@click.option("--period", default="daily")
@click.option("--max-seconds", type=int, required=True)
def limit_add(category, period, max_seconds):
    """Add a time limit."""
    r = _post("/limits", category=category, period=period, max_seconds=max_seconds)
    click.echo(f"Limit #{r.get('id')} added.")


@limit.command("list")
def limit_list():
    """List all limits."""
    for l in _get("/limits"):
        click.echo(f"  #{l['id']}: {l['category']} ({l['period']}) <= {l['max_seconds']}s")


@limit.command("remove")
@click.argument("limit_id", type=int)
def limit_remove(limit_id):
    """Remove a limit."""
    _delete(f"/limits/{limit_id}")
    click.echo(f"Removed #{limit_id}")


@limit.command("status")
def limit_status():
    """Show limit status."""
    for s in _get("/limits/status"):
        mark = "EXCEEDED" if s["exceeded"] else "ok"
        click.echo(f"  {s['category']}: {s['used']}/{s['limit']}s [{mark}]")


# --- Sync ---
@cli.group()
def sync():
    """Cross-device sync."""
    pass


@sync.command("push")
def sync_push():
    """Push local state."""
    r = _post("/sync/push")
    click.echo(f"Push: {r}")


@sync.command("pull")
def sync_pull():
    """Pull remote state."""
    r = _post("/sync/pull")
    click.echo(f"Pull: {r}")


# --- Lockdown ---
@cli.group()
def lockdown():
    """Lockdown mode."""
    pass


@lockdown.command("enter")
@click.option("--minutes", type=int, required=True)
@click.option("--password-hash", default=None)
def lockdown_enter(minutes, password_hash):
    """Enter lockdown."""
    r = _post("/lockdown/enter", duration_minutes=minutes, password_hash=password_hash)
    click.echo(f"Lockdown: {r}")


@lockdown.command("exit")
@click.option("--password", default=None)
def lockdown_exit(password):
    """Try to exit lockdown."""
    r = _post("/lockdown/exit", password=password)
    click.echo(f"Exit: {r.get('ok')}")


@lockdown.command("status")
def lockdown_status():
    """Show lockdown status."""
    r = _get("/lockdown/status")
    click.echo(f"Active: {r.get('active')}, ends at {r.get('end_ts')}")


# --- Sensitivity ---
@cli.group()
def sensitivity():
    """Sensitivity level."""
    pass


@sensitivity.command("get")
def sensitivity_get():
    """Show current sensitivity."""
    r = _get("/sensitivity")
    click.echo(f"Level: {r.get('level')}")


@sensitivity.command("set")
@click.argument("level")
def sensitivity_set(level):
    """Set sensitivity level."""
    _post("/sensitivity", level=level)
    click.echo(f"Set to: {level}")


# --- Digest ---
@cli.group()
def digest():
    """Daily/weekly digests."""
    pass


@digest.command("daily")
def digest_daily():
    """Show daily digest."""
    r = _get("/digest/daily")
    click.echo(r.get("digest", ""))


@digest.command("weekly")
def digest_weekly():
    """Show weekly digest."""
    r = _get("/digest/weekly")
    click.echo(r.get("digest", ""))


# --- Onboarding ---
@cli.group()
def onboarding():
    """First-time setup."""
    pass


@onboarding.command("check")
def onboarding_check():
    """Check onboarding status."""
    r = _get("/onboarding")
    click.echo(f"First run: {r.get('first_run')}")
    click.echo(f"Personas: {r.get('personas')}")


@onboarding.command("apply")
@click.argument("persona")
def onboarding_apply(persona):
    """Apply a persona setup."""
    r = _post("/onboarding/apply", persona=persona)
    click.echo(f"Applied: {r}")


# --- Export formats ---
@cli.group()
def export_fmt():
    """Export data to CSV/MD/HTML."""
    pass


@export_fmt.command("rules-csv")
def export_rules_csv():
    """Export rules as CSV."""
    try:
        r = httpx.get(f"{API}/export/rules.csv", timeout=10)
        click.echo(r.text)
    except httpx.ConnectError:
        click.echo("Error: Sentinel server not running.")
        sys.exit(1)


@export_fmt.command("rules-md")
def export_rules_md():
    """Export rules as Markdown."""
    try:
        r = httpx.get(f"{API}/export/rules.md", timeout=10)
        click.echo(r.text)
    except httpx.ConnectError:
        click.echo("Error: Sentinel server not running.")
        sys.exit(1)


@export_fmt.command("stats-csv")
@click.option("--days", type=int, default=30)
def export_stats_csv(days):
    """Export stats as CSV."""
    try:
        r = httpx.get(f"{API}/export/stats.csv?days={days}", timeout=10)
        click.echo(r.text)
    except httpx.ConnectError:
        click.echo("Error: Sentinel server not running.")
        sys.exit(1)


@export_fmt.command("activity-csv")
@click.option("--days", type=int, default=7)
def export_activity_csv(days):
    """Export activity as CSV."""
    try:
        r = httpx.get(f"{API}/export/activity.csv?days={days}", timeout=10)
        click.echo(r.text)
    except httpx.ConnectError:
        click.echo("Error: Sentinel server not running.")
        sys.exit(1)


@export_fmt.command("report-md")
def export_report_md():
    """Export full report as Markdown."""
    try:
        r = httpx.get(f"{API}/export/report.md", timeout=10)
        click.echo(r.text)
    except httpx.ConnectError:
        click.echo("Error: Sentinel server not running.")
        sys.exit(1)


@export_fmt.command("report-html")
def export_report_html():
    """Export full report as HTML."""
    try:
        r = httpx.get(f"{API}/export/report.html", timeout=10)
        click.echo(r.text)
    except httpx.ConnectError:
        click.echo("Error: Sentinel server not running.")
        sys.exit(1)


if __name__ == "__main__":
    cli()
