"""One config key: privacy_level in {minimal, balanced, full}.

Nothing else in the codebase reads the fine-grained store_urls/titles flags
from the old three-level dict, so they're gone. If the agent needs PII
redaction or data wiping, it can compose those from ai_store + direct SQL;
they were never on the hot path anyway.
"""
from . import db

LEVELS = ("minimal", "balanced", "full")


def get_level(conn) -> str:
    return db.get_config(conn, "privacy_level", "balanced") or "balanced"


def set_level(conn, level: str):
    if level not in LEVELS:
        raise ValueError(f"unknown level: {level}")
    db.set_config(conn, "privacy_level", level)


def is_llm_allowed(conn) -> bool:
    return get_level(conn) != "minimal"
