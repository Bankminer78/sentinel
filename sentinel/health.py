"""System health check — diagnostics for Sentinel."""
import os
import subprocess
import time
from . import db

DAEMON_LABEL = "com.sentinel.daemon"
HOSTS_PATH = "/etc/hosts"
_START_TS = time.time()


def check_api_key(conn) -> bool:
    """True if a Gemini API key is configured."""
    key = db.get_config(conn, "gemini_api_key") or ""
    return bool(key.strip())


def check_database(conn) -> bool:
    """True if the database responds to a trivial query."""
    try:
        conn.execute("SELECT 1").fetchone()
        return True
    except Exception:
        return False


def check_hosts_access() -> bool:
    """True if /etc/hosts is writable by this process."""
    try:
        return os.access(HOSTS_PATH, os.W_OK)
    except Exception:
        return False


def check_daemon_running() -> bool:
    """True if the launchd daemon is loaded."""
    try:
        out = subprocess.run(
            ["launchctl", "list"], capture_output=True, text=True, timeout=5)
        return DAEMON_LABEL in (out.stdout or "")
    except Exception:
        return False


def check_browser_extension(conn, window_seconds: int = 300) -> bool:
    """True if any activity was logged recently (extension sends URLs)."""
    since = time.time() - window_seconds
    row = conn.execute(
        "SELECT 1 FROM activity_log WHERE ts>=? AND (url IS NOT NULL AND url != '') LIMIT 1",
        (since,)).fetchone()
    return row is not None


def get_uptime(conn=None) -> float:
    """Seconds since the health module was imported."""
    return time.time() - _START_TS


def check_health(conn) -> dict:
    """Return a comprehensive health snapshot."""
    issues: list[str] = []
    api_key = check_api_key(conn)
    if not api_key:
        issues.append("gemini api key not set")
    healthy_db = check_database(conn)
    if not healthy_db:
        issues.append("database unhealthy")
    hosts_ok = check_hosts_access()
    if not hosts_ok:
        issues.append("/etc/hosts not writable (run as root or via daemon)")
    daemon = check_daemon_running()
    if not daemon:
        issues.append("launchd daemon not running")
    ext = check_browser_extension(conn)
    if not ext:
        issues.append("browser extension has not reported activity recently")
    rules = db.get_rules(conn, active_only=False) if healthy_db else []
    if not rules:
        issues.append("no rules configured")
    return {
        "api_key_set": api_key,
        "database_healthy": healthy_db,
        "hosts_writable": hosts_ok,
        "daemon_running": daemon,
        "browser_extension_connected": ext,
        "rules_count": len(rules),
        "uptime_seconds": get_uptime(),
        "issues": issues,
    }
