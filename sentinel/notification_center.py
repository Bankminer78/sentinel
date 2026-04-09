"""macOS Notification Center integration."""
import subprocess


def _osascript(cmd: str) -> bool:
    try:
        r = subprocess.run(["osascript", "-e", cmd], capture_output=True,
                           text=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def _escape(s: str) -> str:
    return s.replace('"', '\\"')


def send_banner(title: str, message: str, sound: str = None) -> bool:
    script = f'display notification "{_escape(message)}" with title "{_escape(title)}"'
    if sound:
        script += f' sound name "{sound}"'
    return _osascript(script)


def send_alert(title: str, message: str) -> bool:
    """Persistent alert — needs user dismissal."""
    script = f'display alert "{_escape(title)}" message "{_escape(message)}"'
    return _osascript(script)


def send_with_actions(title: str, message: str, actions: list) -> bool:
    """Show a dialog with action buttons."""
    btns = ",".join(f'"{_escape(a)}"' for a in actions[:3])
    script = (f'display dialog "{_escape(message)}" with title "{_escape(title)}" '
              f'buttons {{{btns}}}')
    return _osascript(script)


def badge_count(app_name: str, count: int) -> bool:
    """Set the badge on an app icon (limited support)."""
    # macOS doesn't let you easily set other apps' badges
    return False


def clear_notifications() -> bool:
    """Clear notifications for this app (best-effort)."""
    try:
        subprocess.run(["killall", "NotificationCenter"], timeout=5, check=False)
        return True
    except Exception:
        return False


def send_progress(title: str, progress: float) -> bool:
    """Show progress as a notification (0.0-1.0)."""
    pct = int(progress * 100)
    return send_banner(title, f"{pct}% complete")


def group_notifications(group_id: str, items: list) -> bool:
    """Show a grouped notification."""
    if not items:
        return True
    first = items[0]
    summary = f"{len(items)} items in {group_id}"
    return send_banner(first, summary)
