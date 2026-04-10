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
    import os, uvicorn
    # Pass the port through the env so the server's startup hook can register
    # it with the http_fetch SSRF self-call defense.
    os.environ["SENTINEL_PORT"] = str(port)
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
