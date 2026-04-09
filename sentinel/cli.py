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


if __name__ == "__main__":
    cli()
