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


if __name__ == "__main__":
    cli()
