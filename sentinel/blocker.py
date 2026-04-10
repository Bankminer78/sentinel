"""Block enforcer — kills apps, blocks domains via /etc/hosts."""
import subprocess, re

HOSTS_MARKER = "# SENTINEL BLOCK"
HOSTS_PATH = "/etc/hosts"

_blocked_domains = set()
_blocked_apps = set()


def block_domain(domain: str):
    """Add domain to /etc/hosts block."""
    _blocked_domains.add(domain)
    _sync_hosts()


def unblock_domain(domain: str, conn=None, force: bool = False) -> bool:
    """Remove a domain from the block list. Returns True on success.

    Honors locks: if a ``no_unblock_domain`` lock covers this domain, the
    request is refused and the function returns False unless ``force=True``.
    Pass ``conn`` from the server or trigger context so the lock check can
    run; without it, the lock layer is bypassed (used by tests / startup).
    """
    if conn is not None and not force:
        from . import locks  # lazy: avoid circular import
        if locks.is_locked(conn, "no_unblock_domain", domain):
            return False
    _blocked_domains.discard(domain)
    _sync_hosts()
    return True


def block_app(bundle_id: str):
    """Add app to blocked list and kill if running."""
    _blocked_apps.add(bundle_id)
    kill_app(bundle_id)


def unblock_app(bundle_id: str, conn=None, force: bool = False) -> bool:
    """Remove an app from the block list. Honors ``no_unblock_app`` locks."""
    if conn is not None and not force:
        from . import locks
        if locks.is_locked(conn, "no_unblock_app", bundle_id):
            return False
    _blocked_apps.discard(bundle_id)
    return True


def kill_app(bundle_id: str):
    """Force-kill an app by bundle ID."""
    try:
        # Get PID from bundle ID
        r = subprocess.run(
            ["osascript", "-e",
             f'tell application "System Events" to unix id of first process whose bundle identifier is "{bundle_id}"'],
            capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            pid = r.stdout.strip()
            subprocess.run(["kill", "-9", pid], timeout=3)
    except Exception:
        pass


def is_blocked_domain(domain: str) -> bool:
    return domain in _blocked_domains


def is_blocked_app(bundle_id: str) -> bool:
    return bundle_id in _blocked_apps


def get_blocked() -> dict:
    return {"domains": list(_blocked_domains), "apps": list(_blocked_apps)}


def enforce(bundle_id: str):
    """Check and kill a blocked app if running."""
    if bundle_id in _blocked_apps:
        kill_app(bundle_id)


def _sync_hosts():
    """Write blocked domains to /etc/hosts. Requires sudo."""
    try:
        with open(HOSTS_PATH, "r") as f:
            content = f.read()
        # Remove existing sentinel block
        content = re.sub(
            rf'{HOSTS_MARKER} START.*?{HOSTS_MARKER} END\n?',
            '', content, flags=re.DOTALL)
        # Add new block
        if _blocked_domains:
            block = f"\n{HOSTS_MARKER} START\n"
            for d in sorted(_blocked_domains):
                block += f"0.0.0.0 {d}\n0.0.0.0 www.{d}\n"
            block += f"{HOSTS_MARKER} END\n"
            content += block
        with open(HOSTS_PATH, "w") as f:
            f.write(content)
        # Flush DNS
        subprocess.run(["dscacheutil", "-flushcache"], timeout=5)
        subprocess.run(["sudo", "killall", "-HUP", "mDNSResponder"], timeout=5)
    except PermissionError:
        # Try with sudo
        try:
            lines = [f"0.0.0.0 {d}\\n0.0.0.0 www.{d}" for d in sorted(_blocked_domains)]
            block_text = "\\n".join(lines)
            subprocess.run(["sudo", "bash", "-c",
                f"sed -i '' '/{HOSTS_MARKER}/,/{HOSTS_MARKER}/d' {HOSTS_PATH} && "
                f"echo '\\n{HOSTS_MARKER} START\\n{block_text}\\n{HOSTS_MARKER} END' >> {HOSTS_PATH} && "
                f"dscacheutil -flushcache && killall -HUP mDNSResponder"],
                timeout=10)
        except Exception:
            pass
    except Exception:
        pass
