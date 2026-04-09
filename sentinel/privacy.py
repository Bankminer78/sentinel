"""Privacy controls — what gets stored, what gets sent to LLM."""
import json, re, time
from . import db

PRIVACY_LEVELS = {
    "minimal": {"store_urls": False, "store_titles": False, "llm_enabled": False},
    "balanced": {"store_urls": True, "store_titles": False, "llm_enabled": True},
    "full": {"store_urls": True, "store_titles": True, "llm_enabled": True},
}

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,2}[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")
_CC_RE = re.compile(r"\b(?:\d[ -]?){13,16}\b")


def set_privacy_level(conn, level: str):
    if level not in PRIVACY_LEVELS:
        raise ValueError(f"unknown level: {level}")
    db.set_config(conn, "privacy_level", level)


def get_privacy_level(conn) -> str:
    return db.get_config(conn, "privacy_level", "balanced") or "balanced"


def get_privacy_config(conn) -> dict:
    return dict(PRIVACY_LEVELS[get_privacy_level(conn)])


def is_llm_allowed(conn) -> bool:
    return get_privacy_config(conn)["llm_enabled"]


def should_store_urls(conn) -> bool:
    return get_privacy_config(conn)["store_urls"]


def should_store_titles(conn) -> bool:
    return get_privacy_config(conn)["store_titles"]


def redact_pii(text: str) -> str:
    if not text:
        return text
    t = _EMAIL_RE.sub("[EMAIL]", text)
    t = _CC_RE.sub("[CARD]", t)
    t = _PHONE_RE.sub("[PHONE]", t)
    return t


def wipe_all_data(conn, confirm: str) -> bool:
    if confirm != "DELETE ALL MY DATA":
        return False
    tables = [r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    for t in tables:
        if t.startswith("sqlite_"):
            continue
        conn.execute(f"DELETE FROM {t}")
    conn.commit()
    return True


def wipe_old_data(conn, days: int = 30) -> int:
    cutoff = time.time() - days * 86400
    cur = conn.execute("DELETE FROM activity_log WHERE ts < ?", (cutoff,))
    conn.commit()
    return cur.rowcount or 0
