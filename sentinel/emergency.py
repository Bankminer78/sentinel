"""Emergency exit — the always-available out switch with a monthly budget.

This is the only thing in the system that can override locks, screen
lockouts, and any other commitment. It exists so the user is never
*genuinely* trapped — but it's loud and rate-limited so impulse can't
spend it lightly.

Design:
- Each call decrements a monthly counter (default 3/month, configurable).
- The limit resets at the start of each calendar month.
- Every exit is logged with reason + timestamp + which kinds were released.
- An exit can target specific lock kinds OR release everything (the default).
- Emergency exits cannot themselves be locked. There is no `no_emergency_exit`
  kind. That would defeat the purpose.
- The agent can READ the remaining count via `emergency_remaining` trigger
  call, but cannot trigger an exit. Only the user (via API) can.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from . import db, ai_store, locks, screen


DEFAULT_MONTHLY_LIMIT = 3
LOG_NAMESPACE = "emergency_exit"


def get_limit(conn) -> int:
    """Read configured monthly limit, or DEFAULT_MONTHLY_LIMIT."""
    raw = db.get_config(conn, "emergency_monthly_limit")
    if raw is None:
        return DEFAULT_MONTHLY_LIMIT
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_MONTHLY_LIMIT


def set_limit(conn, limit: int):
    if not isinstance(limit, int) or limit < 0:
        raise ValueError("limit must be a non-negative integer")
    db.set_config(conn, "emergency_monthly_limit", str(limit))


def _month_start_ts(now: float | None = None) -> float:
    """Timestamp of the start of the current calendar month (local time)."""
    n = datetime.fromtimestamp(now or time.time())
    return datetime(n.year, n.month, 1).timestamp()


def get_used_this_month(conn) -> int:
    """Count exits logged since the start of the current month."""
    cutoff = _month_start_ts()
    docs = ai_store.doc_list(conn, namespace=LOG_NAMESPACE, limit=1000, since=cutoff)
    return len(docs)


def remaining(conn) -> int:
    return max(0, get_limit(conn) - get_used_this_month(conn))


def status(conn) -> dict:
    return {
        "limit": get_limit(conn),
        "used_this_month": get_used_this_month(conn),
        "remaining": remaining(conn),
        "month_start_ts": _month_start_ts(),
    }


def trigger(conn, reason: str, kinds: list[str] | None = None) -> dict:
    """Use one emergency exit. Releases all matching active locks.

    Args:
        reason: required, logged for posterity. Refused if empty.
        kinds: which lock kinds to release. None = release all.

    Returns one of:
        {"ok": True, "released_locks": [...], "remaining": N}
        {"ok": False, "error": "no exits remaining" | "reason required"}
    """
    if not reason or not isinstance(reason, str) or not reason.strip():
        return {"ok": False, "error": "reason required"}
    if remaining(conn) <= 0:
        return {
            "ok": False,
            "error": "no emergency exits remaining this month",
            "next_reset_ts": _next_month_start_ts(),
        }
    # Find all active locks (filtered by kind if requested)
    active = locks.list_active(conn)
    if kinds:
        kind_set = set(kinds)
        targets = [lk for lk in active if lk["kind"] in kind_set]
    else:
        targets = active
    # Release them by stamping released_at directly (bypasses friction)
    now = time.time()
    released_ids = []
    for lk in targets:
        conn.execute("UPDATE locks SET released_at=? WHERE id=?", (now, lk["id"]))
        released_ids.append(lk["id"])
    conn.commit()
    # Also force-end any active screen lockout (unless caller asked for a
    # specific kind set that doesn't include it)
    screen_ended = False
    if kinds is None or "screen_lockout" in (kinds or []):
        screen_ended = screen.end_lockout(conn, force=True)
    # Log the exit BEFORE returning so the counter increments
    ai_store.doc_add(conn, LOG_NAMESPACE, {
        "reason": reason.strip(),
        "kinds": kinds,
        "released_lock_ids": released_ids,
        "released_count": len(released_ids),
        "screen_lockout_ended": screen_ended,
        "ts": now,
    }, tags=["exit"])
    # Audit log entry — payload-free summary, no `reason` text
    try:
        from . import audit
        audit.log(conn, "user", "emergency_exit", {
            "kinds": kinds,
            "released_count": len(released_ids),
            "screen_lockout_ended": screen_ended,
            "remaining_after": max(0, get_limit(conn) - get_used_this_month(conn)),
        })
    except Exception:
        pass
    return {
        "ok": True,
        "released_locks": released_ids,
        "released_count": len(released_ids),
        "screen_lockout_ended": screen_ended,
        "remaining": remaining(conn),
    }


def history(conn, limit: int = 20) -> list:
    """Recent emergency exits, newest first."""
    return ai_store.doc_list(conn, namespace=LOG_NAMESPACE, limit=limit)


def _next_month_start_ts() -> float:
    n = datetime.fromtimestamp(time.time())
    if n.month == 12:
        nxt = datetime(n.year + 1, 1, 1)
    else:
        nxt = datetime(n.year, n.month + 1, 1)
    return nxt.timestamp()
