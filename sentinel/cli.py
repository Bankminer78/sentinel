"""Sentinel CLI — minimal. The user uses the GUI; this is for the daemon."""
import click, sys


@click.group()
def cli():
    """Sentinel daemon CLI. The macOS app uses this to start/stop the server."""
    pass


@cli.command()
@click.option("--port", default=9849, help="Port number")
@click.option("--host", default="127.0.0.1", help="Host")
def serve(port, host):
    """Start the Sentinel server."""
    import os, secrets, uvicorn
    from pathlib import Path

    # Pass the port through the env so the server's startup hook can register
    # it with the http_fetch SSRF self-call defense.
    os.environ["SENTINEL_PORT"] = str(port)

    # Generate a per-launch bearer token for the agent endpoint and write it
    # to a 0600 file the Swift app + GUI can read. Only processes running as
    # this user can open the file. The audit log is the deterrent against
    # any local malware that finds it.
    token_dir = Path.home() / "Library" / "Application Support" / "Sentinel"
    token_dir.mkdir(parents=True, exist_ok=True)
    token_path = token_dir / "agent.token"
    token = secrets.token_urlsafe(32)
    token_path.write_text(token)
    token_path.chmod(0o600)
    os.environ["SENTINEL_AGENT_TOKEN"] = token

    # The agent's working directory — Claude's Bash tool runs scripts here.
    workdir = Path.home() / ".config" / "sentinel" / "agent_workdir"
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "policies").mkdir(exist_ok=True)
    cron_toml = workdir / "cron.toml"
    if not cron_toml.exists():
        cron_toml.write_text("# Scheduled policies — written by Claude.\n# See AGENT.md.\n")

    uvicorn.run("sentinel.server:app", host=host, port=port, log_level="info")


@cli.command()
def status():
    """Quick status check."""
    import httpx
    try:
        r = httpx.get("http://localhost:9849/health", timeout=3)
        click.echo(r.json())
    except httpx.ConnectError:
        click.echo("Server not running")
        sys.exit(1)


if __name__ == "__main__":
    cli()
