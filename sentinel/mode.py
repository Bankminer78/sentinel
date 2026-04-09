"""Mode switching — quick presets that apply rule sets and block categories."""
from . import db

MODES = {
    "work": {
        "rules": ["block social", "block streaming", "block gaming"],
        "block_categories": ["social", "streaming", "gaming"],
    },
    "study": {
        "rules": ["block social", "block streaming", "block gaming"],
        "block_categories": ["social", "streaming", "gaming"],
    },
    "relax": {
        "rules": [],
        "block_categories": [],
    },
    "sleep": {
        "rules": ["block social", "block streaming", "block gaming", "block adult"],
        "block_categories": ["social", "streaming", "gaming", "adult"],
    },
    "family": {
        "rules": ["block adult", "block gaming"],
        "block_categories": ["adult", "gaming"],
    },
}

_MODE_KEY = "current_mode"
_DEFAULT_MODE = "relax"


def switch_mode(conn, mode_name: str) -> dict:
    if mode_name not in MODES:
        return {"ok": False, "error": f"unknown mode: {mode_name}"}
    db.set_config(conn, _MODE_KEY, mode_name)
    m = MODES[mode_name]
    return {"ok": True, "mode": mode_name, "rules": list(m["rules"]),
            "block_categories": list(m["block_categories"])}


def get_current_mode(conn) -> str:
    return db.get_config(conn, _MODE_KEY, _DEFAULT_MODE)


def list_modes() -> list:
    return [{"name": n, "rules": list(m["rules"]),
             "block_categories": list(m["block_categories"])}
            for n, m in MODES.items()]


def is_blocked_in_mode(conn, domain_category: str) -> bool:
    mode = get_current_mode(conn)
    m = MODES.get(mode, MODES[_DEFAULT_MODE])
    return domain_category in m["block_categories"]
