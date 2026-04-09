"""Sensitivity / strictness modes — strict, normal, lax."""
from . import db

LEVELS = {
    "strict": {"auto_block_threshold": 0.5, "allow_negotiation": False, "penalty_multiplier": 2.0},
    "normal": {"auto_block_threshold": 0.7, "allow_negotiation": True, "penalty_multiplier": 1.0},
    "lax":    {"auto_block_threshold": 0.9, "allow_negotiation": True, "penalty_multiplier": 0.5},
}

DEFAULT = "normal"
_CONFIG_KEY = "sensitivity_level"


def set_sensitivity(conn, level: str):
    """Set sensitivity level. Raises ValueError on invalid level."""
    if level not in LEVELS:
        raise ValueError(f"unknown sensitivity level: {level}")
    db.set_config(conn, _CONFIG_KEY, level)


def get_sensitivity(conn) -> str:
    """Return current sensitivity level, defaulting to 'normal'."""
    level = db.get_config(conn, _CONFIG_KEY, DEFAULT)
    return level if level in LEVELS else DEFAULT


def get_sensitivity_config(conn) -> dict:
    """Return the active sensitivity config dict."""
    return dict(LEVELS[get_sensitivity(conn)])


def list_levels() -> list[str]:
    return list(LEVELS.keys())


def apply_penalty(conn, base_amount: float) -> float:
    """Scale a penalty amount by the current multiplier."""
    return base_amount * get_sensitivity_config(conn)["penalty_multiplier"]


def is_negotiation_allowed(conn) -> bool:
    return get_sensitivity_config(conn)["allow_negotiation"]


def auto_block_threshold(conn) -> float:
    return get_sensitivity_config(conn)["auto_block_threshold"]
