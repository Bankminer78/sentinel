"""Tamper detection for /etc/hosts block entries."""
import threading, time, os
from . import blocker

HOSTS_PATH = "/etc/hosts"
BACKUP_PATH = "/etc/hosts.sentinel-backup"
MARKER = "# SENTINEL BLOCK"
_running = False
_thread = None

def check_hosts_intact(hosts_path=HOSTS_PATH) -> bool:
    """Check if our block markers are still in /etc/hosts."""
    try:
        with open(hosts_path) as f:
            content = f.read()
        # If we have blocked domains, our markers should be present
        if blocker._blocked_domains:
            return f"{MARKER} START" in content and f"{MARKER} END" in content
        return True
    except Exception:
        return False

def restore_hosts_block():
    """Re-apply block entries if they've been tampered with."""
    if blocker._blocked_domains:
        blocker._sync_hosts()

def periodic_check(interval=5, hosts_path=HOSTS_PATH):
    """Background check loop."""
    global _running
    while _running:
        if not check_hosts_intact(hosts_path):
            restore_hosts_block()
        time.sleep(interval)

def start_watcher(interval=5):
    """Start background tamper-detection thread."""
    global _running, _thread
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=periodic_check, args=(interval,), daemon=True)
    _thread.start()

def stop_watcher():
    global _running
    _running = False
