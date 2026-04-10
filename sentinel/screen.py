"""Frozen Turkey — fullscreen lockout effector.

The Python side is just state management: write the lockout window
(message + until_ts) to the config table. The macOS Sentinel.app polls
``GET /screen-lock/state`` every second and, when active, takes over
every screen with a borderless full-screen NSWindow.

End-of-lockout: when ``until_ts`` passes, the next state poll returns
inactive and the Swift app dismisses the window.

Early termination: only the emergency exit primitive can call
``end_lockout()``. The /screen-lock/end endpoint is intentionally tied
to the emergency budget — that's the whole point of Frozen Turkey.

If the Swift app isn't running, the lockout state still exists in the
DB but no UI takes over. That's a graceful degradation: a future Sentinel
launch will read the state and lock the screen for whatever time remains.
"""
from __future__ import annotations

import json
import time

from . import db


CFG_KEY = "screen_lockout"


def get_state(conn) -> dict:
    """Current lockout state. Always returns ``{active, until_ts, message}``."""
    raw = db.get_config(conn, CFG_KEY)
    if not raw:
        return {"active": False, "until_ts": None, "message": None}
    try:
        s = json.loads(raw)
    except (TypeError, ValueError):
        return {"active": False, "until_ts": None, "message": None}
    until = s.get("until_ts") or 0
    if until <= time.time():
        # Expired — clean up and return inactive
        db.set_config(conn, CFG_KEY, "")
        return {"active": False, "until_ts": None, "message": None}
    return {
        "active": True,
        "until_ts": until,
        "message": s.get("message", ""),
        "remaining_seconds": int(until - time.time()),
        "started_at": s.get("started_at"),
    }


def lock(conn, duration_seconds: int, message: str = "Focus mode") -> dict:
    """Start (or extend) a screen lockout.

    If a lockout is already active, extends it to whichever ``until_ts`` is
    later. This means the agent can't shorten an active lockout — only
    emergency_exit can.
    """
    if not isinstance(duration_seconds, (int, float)) or duration_seconds < 1:
        raise ValueError("duration_seconds must be >= 1")
    now = time.time()
    cur = get_state(conn)
    new_until = now + duration_seconds
    if cur["active"] and cur["until_ts"] > new_until:
        new_until = cur["until_ts"]
        message = cur.get("message") or message
    state = {
        "active": True,
        "until_ts": new_until,
        "message": message,
        "started_at": cur.get("started_at") if cur["active"] else now,
    }
    db.set_config(conn, CFG_KEY, json.dumps(state))
    return get_state(conn)


def end_lockout(conn, force: bool = False) -> bool:
    """Clear the lockout state.

    Refuses unless ``force=True`` or the lockout has expired naturally.
    Only the emergency-exit endpoint passes ``force=True``.
    """
    cur = get_state(conn)
    if not cur["active"]:
        return True
    if not force:
        return False
    db.set_config(conn, CFG_KEY, "")
    return True


def is_active(conn) -> bool:
    return get_state(conn)["active"]
