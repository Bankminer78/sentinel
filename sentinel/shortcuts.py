"""macOS Shortcuts integration — trigger Sentinel via Shortcuts.app."""
import subprocess, json
from pathlib import Path


SHORTCUT_ACTIONS = [
    "start_focus", "stop_focus", "start_pomodoro", "add_rule",
    "check_score", "morning_briefing", "log_mood", "log_water",
    "start_deep_work", "end_deep_work",
]


def list_available_actions() -> list:
    """Actions that can be called from Shortcuts."""
    return SHORTCUT_ACTIONS


def generate_shortcut_url(action: str, params: dict = None) -> str:
    """Generate a URL scheme for the action."""
    base = "sentinel://"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{base}{action}?{query}"
    return f"{base}{action}"


def list_installed_shortcuts() -> list:
    """List macOS Shortcuts via shortcuts CLI."""
    try:
        r = subprocess.run(["shortcuts", "list"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            return [s.strip() for s in r.stdout.splitlines() if s.strip()]
    except Exception:
        pass
    return []


def run_shortcut(name: str, input_text: str = "") -> str:
    """Run a macOS shortcut by name."""
    try:
        cmd = ["shortcuts", "run", name]
        if input_text:
            r = subprocess.run(cmd, input=input_text, capture_output=True, text=True, timeout=30)
        else:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def export_shortcut_definitions() -> dict:
    """Export shortcut action definitions as a dict."""
    return {
        "actions": [
            {"id": "start_focus", "name": "Start Focus Session",
             "inputs": ["minutes"], "returns": "session_id"},
            {"id": "stop_focus", "name": "Stop Focus Session",
             "inputs": [], "returns": "ok"},
            {"id": "start_pomodoro", "name": "Start Pomodoro",
             "inputs": ["work", "break"], "returns": "session_id"},
            {"id": "add_rule", "name": "Add Rule",
             "inputs": ["text"], "returns": "rule_id"},
            {"id": "check_score", "name": "Get Productivity Score",
             "inputs": [], "returns": "score"},
            {"id": "log_mood", "name": "Log Mood",
             "inputs": ["mood"], "returns": "mood_id"},
            {"id": "log_water", "name": "Log Water",
             "inputs": ["ounces"], "returns": "ok"},
        ]
    }


def is_shortcuts_available() -> bool:
    """Check if the Shortcuts CLI is available."""
    try:
        r = subprocess.run(["which", "shortcuts"], capture_output=True, text=True, timeout=3)
        return r.returncode == 0
    except Exception:
        return False
