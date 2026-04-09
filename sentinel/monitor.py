"""Activity monitor — tracks foreground app and browser URL on macOS."""
import subprocess, re, time, threading

# Current activity state (updated by polling thread)
_current = {"app": "", "title": "", "url": "", "domain": "", "bundle_id": ""}
_running = False
_thread = None
_browser_url = ""  # Set externally by the server when extension reports


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    if not url:
        return ""
    m = re.match(r'^(?:https?://)?(?:www\.)?([^/\?#]+)', url.lower())
    return m.group(1) if m else ""


def _poll():
    """Poll foreground app via macOS APIs."""
    global _current
    try:
        from AppKit import NSWorkspace
        while _running:
            app = NSWorkspace.sharedWorkspace().frontmostApplication()
            if app:
                name = app.localizedName() or ""
                bid = app.bundleIdentifier() or ""
                # Get window title via AppleScript (simpler than Accessibility API)
                title = ""
                try:
                    r = subprocess.run(
                        ["osascript", "-e",
                         f'tell application "System Events" to get name of first window of (first process whose bundle identifier is "{bid}")'],
                        capture_output=True, text=True, timeout=2)
                    if r.returncode == 0:
                        title = r.stdout.strip()
                except Exception:
                    pass
                # Get browser URL if it's a browser
                url = _browser_url
                if not url and bid in ("com.google.Chrome", "com.apple.Safari",
                                       "company.thebrowser.Browser", "com.brave.Browser"):
                    try:
                        script = {
                            "com.google.Chrome": 'tell application "Google Chrome" to return URL of active tab of front window',
                            "com.apple.Safari": 'tell application "Safari" to return URL of front document',
                            "company.thebrowser.Browser": 'tell application "Arc" to return URL of active tab of front window',
                            "com.brave.Browser": 'tell application "Brave Browser" to return URL of active tab of front window',
                        }.get(bid, "")
                        if script:
                            r = subprocess.run(["osascript", "-e", script],
                                               capture_output=True, text=True, timeout=2)
                            if r.returncode == 0:
                                url = r.stdout.strip()
                    except Exception:
                        pass
                _current = {
                    "app": name, "title": title, "url": url,
                    "domain": _extract_domain(url), "bundle_id": bid
                }
            time.sleep(1)
    except ImportError:
        # Not on macOS — fall back to doing nothing
        while _running:
            time.sleep(1)


def start():
    """Start monitoring in background thread."""
    global _running, _thread
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=_poll, daemon=True)
    _thread.start()


def stop():
    """Stop monitoring."""
    global _running
    _running = False


def get_current() -> dict:
    """Get current foreground activity."""
    return dict(_current)


def set_browser_url(url: str):
    """Called by server when browser extension reports a URL."""
    global _browser_url
    _browser_url = url
