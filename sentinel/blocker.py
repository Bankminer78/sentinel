"""Block enforcer — blocks domains via /etc/hosts, kills apps.

Blocks PERSIST in SQLite and survive daemon restarts. On startup,
load_from_db() reads them into memory AND syncs to /etc/hosts.

/etc/hosts blocking works across ALL browsers, ALL incognito modes,
ALL apps — it's DNS-level. No browser extension needed for enforcement
(the extension is just for activity logging).

First-run installs /etc/sudoers.d/sentinel so the daemon can write
/etc/hosts without a password prompt ever again. One macOS auth dialog
at install, then passwordless forever. Like Cold Turkey.
"""
import os
import subprocess
import time
from pathlib import Path

HOSTS_MARKER = "# SENTINEL BLOCK"
HOSTS_PATH = "/etc/hosts"
SUDOERS_PATH = "/etc/sudoers.d/sentinel"

_blocked_domains: set[str] = set()
_blocked_apps: set[str] = set()


# --- One-time sudo setup ---

def ensure_sudo_access():
    """Install a sudoers rule so the daemon can write /etc/hosts without
    a password. Shows macOS's native auth dialog ONCE at first install.
    Subsequent runs skip if the sudoers file already exists.
    """
    if os.path.exists(SUDOERS_PATH):
        return True  # already set up
    user = os.environ.get("USER", "")
    if not user:
        return False
    # The sudoers rule grants passwordless sudo for ONLY these commands:
    # - tee /etc/hosts (write the file)
    # - dscacheutil -flushcache (flush DNS)
    # - killall -HUP mDNSResponder (flush DNS on newer macOS)
    rule = (
        f"{user} ALL=(root) NOPASSWD: /usr/bin/tee /etc/hosts, "
        f"/usr/sbin/dscacheutil -flushcache, "
        f"/usr/bin/killall -HUP mDNSResponder\n"
    )
    # Use osascript to elevate and write the sudoers file.
    # This pops macOS's native auth dialog (Touch ID or password) ONCE.
    escaped_rule = rule.replace("'", "'\\''")
    script = (
        f"printf '{escaped_rule}' > {SUDOERS_PATH} && "
        f"chmod 0440 {SUDOERS_PATH} && "
        f"chown root:wheel {SUDOERS_PATH} && "
        f"echo ok"
    )
    try:
        r = subprocess.run(
            ["osascript", "-e",
             f'do shell script "{script}" with administrator privileges'],
            capture_output=True, text=True, timeout=60,
        )
        return r.returncode == 0 and "ok" in r.stdout
    except Exception:
        return False


# --- Persistence (SQLite) ---

def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS blocked_domains (
        domain TEXT PRIMARY KEY,
        blocked_at REAL NOT NULL
    )""")


def load_from_db(conn):
    """Load persisted blocks into memory + sync to /etc/hosts. Call at startup."""
    global _blocked_domains
    _ensure_table(conn)
    rows = conn.execute("SELECT domain FROM blocked_domains").fetchall()
    _blocked_domains = {r["domain"] for r in rows}
    if _blocked_domains:
        _sync_hosts()


def _db_add(conn, domain: str):
    if conn is None:
        return
    _ensure_table(conn)
    conn.execute(
        "INSERT OR IGNORE INTO blocked_domains (domain, blocked_at) VALUES (?, ?)",
        (domain, time.time()))
    conn.commit()


def _db_remove(conn, domain: str):
    if conn is None:
        return
    _ensure_table(conn)
    conn.execute("DELETE FROM blocked_domains WHERE domain = ?", (domain,))
    conn.commit()


# --- Audit ---

def _audit(conn, actor, primitive, args, status="ok"):
    if conn is None:
        return
    try:
        from . import audit
        audit.log(conn, actor, primitive, args, status)
    except Exception:
        pass


# --- Block / unblock ---

def block_domain(domain: str, conn=None, actor: str = "system"):
    """Block a domain. Persists in DB + writes /etc/hosts."""
    domain = domain.strip().lower()
    if not domain:
        return
    _blocked_domains.add(domain)
    _db_add(conn, domain)
    _sync_hosts()
    _audit(conn, actor, "block_domain", {"domain": domain})


def unblock_domain(domain: str, conn=None, force: bool = False,
                   actor: str = "system") -> bool:
    """Remove a domain. Returns False if locked."""
    domain = domain.strip().lower()
    if conn is not None and not force:
        from . import locks
        if locks.is_locked(conn, "no_unblock_domain", domain):
            _audit(conn, actor, "unblock_domain",
                   {"domain": domain}, status="locked")
            return False
    _blocked_domains.discard(domain)
    _db_remove(conn, domain)
    _sync_hosts()
    _audit(conn, actor, "unblock_domain", {"domain": domain},
           status="forced" if force else "ok")
    return True


def block_app(bundle_id: str, conn=None, actor: str = "system"):
    _blocked_apps.add(bundle_id)
    kill_app(bundle_id)
    _audit(conn, actor, "block_app", {"bundle_id": bundle_id})


def unblock_app(bundle_id: str, conn=None, force: bool = False,
                actor: str = "system") -> bool:
    if conn is not None and not force:
        from . import locks
        if locks.is_locked(conn, "no_unblock_app", bundle_id):
            _audit(conn, actor, "unblock_app",
                   {"bundle_id": bundle_id}, status="locked")
            return False
    _blocked_apps.discard(bundle_id)
    _audit(conn, actor, "unblock_app", {"bundle_id": bundle_id},
           status="forced" if force else "ok")
    return True


def kill_app(bundle_id: str):
    try:
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
    return domain.strip().lower() in _blocked_domains


def is_blocked_app(bundle_id: str) -> bool:
    return bundle_id in _blocked_apps


def get_blocked() -> dict:
    return {"domains": sorted(_blocked_domains), "apps": sorted(_blocked_apps)}


def enforce(bundle_id: str):
    if bundle_id in _blocked_apps:
        kill_app(bundle_id)


# --- /etc/hosts writer ---

def _sync_hosts():
    """Write ALL blocked domains to /etc/hosts via passwordless sudo.

    Requires ensure_sudo_access() to have run once (which installs
    /etc/sudoers.d/sentinel). After that, this never prompts.

    Works across ALL browsers, incognito, all apps — it's DNS-level.
    """
    try:
        # Read current hosts file
        with open(HOSTS_PATH, "r") as f:
            original = f.read()
    except Exception:
        return

    # Remove existing Sentinel block
    import re
    cleaned = re.sub(
        rf'\n?{HOSTS_MARKER} START.*?{HOSTS_MARKER} END\n?',
        '', original, flags=re.DOTALL)

    # Build new block section
    if _blocked_domains:
        block = f"\n{HOSTS_MARKER} START\n"
        for d in sorted(_blocked_domains):
            block += f"0.0.0.0 {d}\n"
            if not d.startswith("www."):
                block += f"0.0.0.0 www.{d}\n"
        block += f"{HOSTS_MARKER} END\n"
        new_content = cleaned + block
    else:
        new_content = cleaned

    if new_content.strip() == original.strip():
        return  # no change needed

    # Write via sudo tee (passwordless thanks to /etc/sudoers.d/sentinel)
    try:
        proc = subprocess.run(
            ["sudo", "tee", HOSTS_PATH],
            input=new_content.encode(),
            capture_output=True,
            timeout=10,
        )
        if proc.returncode == 0:
            # Flush DNS cache
            subprocess.run(["dscacheutil", "-flushcache"],
                           capture_output=True, timeout=5)
            subprocess.run(["sudo", "killall", "-HUP", "mDNSResponder"],
                           capture_output=True, timeout=5)
    except Exception:
        pass
