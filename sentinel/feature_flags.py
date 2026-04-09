"""Feature flags — toggle experimental features."""
import time, json
from . import db


DEFAULT_FLAGS = {
    "experimental_vision": False,
    "advanced_nlp": True,
    "ai_coach": True,
    "web_dashboard": True,
    "mobile_ui": True,
    "telemetry": False,
    "auto_backup": True,
    "realtime_sse": True,
    "gamification": True,
    "burnout_detection": True,
    "coaching_notifications": False,
    "rule_suggestions": True,
    "smart_classification": True,
    "pomodoro_auto": False,
}


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS feature_flags (
        name TEXT PRIMARY KEY, enabled INTEGER, updated_at REAL
    )""")


def get_flag(conn, name: str) -> bool:
    _ensure_table(conn)
    r = conn.execute("SELECT enabled FROM feature_flags WHERE name=?", (name,)).fetchone()
    if r is not None:
        return bool(r["enabled"])
    return DEFAULT_FLAGS.get(name, False)


def set_flag(conn, name: str, enabled: bool):
    _ensure_table(conn)
    conn.execute(
        "INSERT OR REPLACE INTO feature_flags (name, enabled, updated_at) VALUES (?, ?, ?)",
        (name, 1 if enabled else 0, time.time()))
    conn.commit()


def get_all_flags(conn) -> dict:
    _ensure_table(conn)
    custom = {r["name"]: bool(r["enabled"]) for r in
              conn.execute("SELECT name, enabled FROM feature_flags").fetchall()}
    return {**DEFAULT_FLAGS, **custom}


def reset_flag(conn, name: str):
    _ensure_table(conn)
    conn.execute("DELETE FROM feature_flags WHERE name=?", (name,))
    conn.commit()


def reset_all(conn):
    _ensure_table(conn)
    conn.execute("DELETE FROM feature_flags")
    conn.commit()


def is_enabled(conn, name: str) -> bool:
    return get_flag(conn, name)


def enable(conn, name: str):
    set_flag(conn, name, True)


def disable(conn, name: str):
    set_flag(conn, name, False)


def list_flags() -> list:
    return list(DEFAULT_FLAGS.keys())
