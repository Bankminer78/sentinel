"""Global hotkey definitions for the Sentinel app."""
import json
from . import db


DEFAULT_HOTKEYS = {
    "quick_add_rule": {"keys": "cmd+shift+r", "description": "Quick add a rule"},
    "start_pomodoro": {"keys": "cmd+shift+p", "description": "Start pomodoro"},
    "start_focus": {"keys": "cmd+shift+f", "description": "Start focus session"},
    "toggle_block": {"keys": "cmd+shift+b", "description": "Toggle blocking"},
    "open_dashboard": {"keys": "cmd+shift+d", "description": "Open dashboard"},
    "log_mood": {"keys": "cmd+shift+m", "description": "Log mood"},
    "log_water": {"keys": "cmd+shift+w", "description": "Log water"},
    "quick_journal": {"keys": "cmd+shift+j", "description": "Quick journal entry"},
    "add_todo": {"keys": "cmd+shift+t", "description": "Add todo"},
    "show_score": {"keys": "cmd+shift+s", "description": "Show today's score"},
}


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS hotkey_overrides (
        action TEXT PRIMARY KEY, keys TEXT
    )""")


def list_hotkeys(conn) -> list:
    _ensure_table(conn)
    overrides = {r["action"]: r["keys"] for r in
                 conn.execute("SELECT * FROM hotkey_overrides").fetchall()}
    result = []
    for action, info in DEFAULT_HOTKEYS.items():
        keys = overrides.get(action, info["keys"])
        result.append({"action": action, "keys": keys, "description": info["description"]})
    return result


def get_hotkey(conn, action: str) -> str:
    _ensure_table(conn)
    r = conn.execute("SELECT keys FROM hotkey_overrides WHERE action=?", (action,)).fetchone()
    if r:
        return r["keys"]
    info = DEFAULT_HOTKEYS.get(action)
    return info["keys"] if info else ""


def set_hotkey(conn, action: str, keys: str) -> bool:
    _ensure_table(conn)
    if action not in DEFAULT_HOTKEYS:
        return False
    conn.execute(
        "INSERT OR REPLACE INTO hotkey_overrides (action, keys) VALUES (?, ?)",
        (action, keys))
    conn.commit()
    return True


def reset_hotkey(conn, action: str):
    _ensure_table(conn)
    conn.execute("DELETE FROM hotkey_overrides WHERE action=?", (action,))
    conn.commit()


def reset_all(conn):
    _ensure_table(conn)
    conn.execute("DELETE FROM hotkey_overrides")
    conn.commit()


def available_actions() -> list:
    return list(DEFAULT_HOTKEYS.keys())


def validate_hotkey(keys: str) -> bool:
    """Basic validation of hotkey format."""
    if not keys:
        return False
    parts = keys.lower().split("+")
    modifiers = {"cmd", "ctrl", "shift", "alt", "option", "meta"}
    has_modifier = any(p in modifiers for p in parts)
    has_key = any(p not in modifiers and len(p) >= 1 for p in parts)
    return has_modifier and has_key


def count_hotkeys() -> int:
    return len(DEFAULT_HOTKEYS)


def export_hotkeys(conn) -> str:
    return json.dumps(list_hotkeys(conn), indent=2)
