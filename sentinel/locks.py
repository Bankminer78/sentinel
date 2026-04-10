"""Locks — write-once commitments with optional friction-gated early release.

The most distinctive Cold Turkey feature: once a commitment is made, nothing
in the running system can undo it until time has passed — not the API, not a
trigger the agent wrote, not a config flip, not even killing and restarting
the daemon (locks live in SQLite, loaded on every check).

A lock is a (kind, target, until_ts, friction?) row that:
- Cannot be modified after creation. There is no UPDATE.
- Cannot be deleted via the API while active. The only ways out are
  waiting for ``until_ts`` or completing the friction gate (if any).
- Is consulted on every protected operation (currently: unblock_domain,
  unblock_app, triggers.delete + set_enabled-off).
- Is fully agent-composable: triggers can ``create_lock`` and ``is_locked``
  on any kind they invent. The system enforces the well-known kinds; the
  agent enforces the rest.

Built-in kinds the system enforces directly:
- ``no_unblock_domain``  — blocker.unblock_domain refuses to remove ``target``
- ``no_unblock_app``     — blocker.unblock_app refuses to remove ``target``
- ``no_delete_trigger``  — triggers.delete refuses to remove ``target``
- ``no_disable_trigger`` — triggers.set_enabled(False) refuses on ``target``

Custom kinds: the agent picks any string and calls ``is_locked(kind, target)``
inside its own triggers. Use this for "no_pause", "no_reduce_privacy",
"no_modify_kv:tr:focus.streak", or anything else.

Friction types:
- ``{"type": "wait", "seconds": N}``    — request_release starts a timer;
  complete_release succeeds only after N seconds elapse
- ``{"type": "type_text", "chars": N}`` — request_release returns N random
  chars; complete_release requires the user to type them back exactly
- ``None``                              — no early release; only ``until_ts``
  expiry frees the lock

This is a deterrent against your own impulse, not against an adversary with
sqlite3. Cold Turkey has the same property — anyone with shell access can
edit its config files. The point is to make casual circumvention harder than
the discomfort the lock is protecting you from.
"""
from __future__ import annotations

import json
import secrets
import string
import time
from typing import Any


# --- Schema ---

def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS locks (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        kind TEXT NOT NULL,
        target TEXT,
        until_ts REAL NOT NULL,
        friction TEXT,
        challenge_token TEXT,
        challenge_started_at REAL,
        challenge_expected TEXT,
        created_at REAL NOT NULL,
        released_at REAL
    )""")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_locks_kind_target "
        "ON locks(kind, target, released_at)")


# --- Friction validation ---

VALID_FRICTION_TYPES = {"wait", "type_text"}
TYPE_TEXT_MIN_CHARS = 10
TYPE_TEXT_MAX_CHARS = 1000


def _validate_friction(friction: dict | None) -> dict | None:
    if friction is None:
        return None
    if not isinstance(friction, dict) or "type" not in friction:
        raise ValueError("friction must be a dict with 'type'")
    t = friction["type"]
    if t not in VALID_FRICTION_TYPES:
        raise ValueError(f"unknown friction type: {t}")
    if t == "wait":
        sec = friction.get("seconds", 0)
        if not isinstance(sec, (int, float)) or sec < 1:
            raise ValueError("wait friction needs seconds >= 1")
        return {"type": "wait", "seconds": int(sec)}
    if t == "type_text":
        chars = friction.get("chars", 0)
        if not isinstance(chars, int) or chars < TYPE_TEXT_MIN_CHARS:
            raise ValueError(f"type_text friction needs chars >= {TYPE_TEXT_MIN_CHARS}")
        if chars > TYPE_TEXT_MAX_CHARS:
            raise ValueError(f"type_text friction max chars is {TYPE_TEXT_MAX_CHARS}")
        return {"type": "type_text", "chars": chars}
    return None  # unreachable


# --- CRUD ---

def create(conn, name: str, kind: str, target: str | None,
           duration_seconds: int, friction: dict | None = None,
           actor: str = "user") -> int:
    """Create a lock. Returns its id.

    Args:
        name: human-readable label, shown in the UI
        kind: protected operation, e.g. "no_unblock_domain" or any custom string
        target: specific resource the lock applies to (domain, app id, trigger
            name). Pass ``None`` for a kind-wide lock that matches any target.
        duration_seconds: how long until the lock expires
        friction: optional gate for early release. ``None`` = no escape.
        actor: who created the lock — recorded in audit log.
    """
    _ensure_table(conn)
    if not name or not isinstance(name, str):
        raise ValueError("name required")
    if not kind or not isinstance(kind, str):
        raise ValueError("kind required")
    if not isinstance(duration_seconds, (int, float)) or duration_seconds < 1:
        raise ValueError("duration_seconds must be >= 1")
    fr = _validate_friction(friction)
    until_ts = time.time() + duration_seconds
    cur = conn.execute(
        "INSERT INTO locks (name, kind, target, until_ts, friction, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (name, kind, target, until_ts,
         json.dumps(fr) if fr else None, time.time()))
    conn.commit()
    try:
        from . import audit
        audit.log(conn, actor, "lock.create", {
            "lock_id": cur.lastrowid, "kind": kind, "target": target,
            "duration_seconds": int(duration_seconds),
            "has_friction": fr is not None,
        })
    except Exception:
        pass
    return cur.lastrowid


def get(conn, lock_id: int) -> dict | None:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM locks WHERE id=?", (lock_id,)).fetchone()
    return _row_to_dict(r) if r else None


def list_active(conn, kind: str | None = None) -> list:
    """All locks not yet expired or released, optionally filtered by kind."""
    _ensure_table(conn)
    now = time.time()
    if kind:
        rows = conn.execute(
            "SELECT * FROM locks WHERE kind=? AND released_at IS NULL "
            "AND until_ts > ? ORDER BY until_ts",
            (kind, now)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM locks WHERE released_at IS NULL AND until_ts > ? "
            "ORDER BY until_ts", (now,)).fetchall()
    return [_row_to_dict(r) for r in rows]


def list_all(conn, limit: int = 100) -> list:
    """All locks including expired/released, newest first."""
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM locks ORDER BY created_at DESC LIMIT ?",
        (limit,)).fetchall()
    return [_row_to_dict(r) for r in rows]


def is_locked(conn, kind: str, target: str | None = None) -> bool:
    """True if any active lock matches kind+target.

    A kind-wide lock (target=NULL in the row) matches *every* target. So
    ``is_locked("no_unblock_domain", "youtube.com")`` returns True both for
    a lock on "youtube.com" specifically and for a lock with target=NULL
    that covers all domains.
    """
    _ensure_table(conn)
    now = time.time()
    if target is None:
        r = conn.execute(
            "SELECT 1 FROM locks WHERE kind=? AND released_at IS NULL "
            "AND until_ts > ? LIMIT 1",
            (kind, now)).fetchone()
    else:
        r = conn.execute(
            "SELECT 1 FROM locks WHERE kind=? AND released_at IS NULL "
            "AND until_ts > ? AND (target=? OR target IS NULL) LIMIT 1",
            (kind, now, target)).fetchone()
    return r is not None


def cleanup_expired(conn) -> int:
    """Mark expired locks as released. Returns count released.

    Called by the trigger worker on every tick so list_active stays small.
    """
    _ensure_table(conn)
    now = time.time()
    cur = conn.execute(
        "UPDATE locks SET released_at=? "
        "WHERE released_at IS NULL AND until_ts <= ?",
        (now, now))
    conn.commit()
    return cur.rowcount or 0


def delete(conn, lock_id: int) -> bool:
    """Delete a lock row.

    Refuses to delete an active lock. The caller must wait for expiry or
    complete the friction gate first.
    """
    _ensure_table(conn)
    lk = get(conn, lock_id)
    if not lk:
        return False
    if lk.get("released_at") is None and lk["until_ts"] > time.time():
        return False
    conn.execute("DELETE FROM locks WHERE id=?", (lock_id,))
    conn.commit()
    return True


# --- Friction gate ---

def request_release(conn, lock_id: int) -> dict:
    """Begin the early-release process.

    Returns one of:
    - ``{"released": True, "reason": "expired"}`` if the lock already expired
    - ``{"already_released": True}`` if a prior release already completed
    - ``{"error": ...}`` if the lock has no friction or doesn't exist
    - ``{"challenge": {...}, "lock_id": id}`` with the challenge spec
    """
    _ensure_table(conn)
    lk = get(conn, lock_id)
    if not lk:
        return {"error": "not found"}
    if lk.get("released_at") is not None:
        return {"already_released": True}
    if lk["until_ts"] <= time.time():
        conn.execute("UPDATE locks SET released_at=? WHERE id=?",
                     (time.time(), lock_id))
        conn.commit()
        return {"released": True, "reason": "expired"}
    friction = lk.get("friction")
    if not friction:
        return {
            "error": "no early release available — wait for expiry",
            "until_ts": lk["until_ts"],
        }
    token = secrets.token_urlsafe(16)
    now = time.time()
    expected: str | None = None
    if friction["type"] == "type_text":
        alphabet = string.ascii_letters + string.digits
        expected = "".join(secrets.choice(alphabet) for _ in range(friction["chars"]))
    conn.execute(
        "UPDATE locks SET challenge_token=?, challenge_started_at=?, "
        "challenge_expected=? WHERE id=?",
        (token, now, expected, lock_id))
    conn.commit()
    spec: dict[str, Any] = {"token": token, "type": friction["type"]}
    if friction["type"] == "wait":
        spec["wait_seconds"] = friction["seconds"]
        spec["unlock_at"] = now + friction["seconds"]
    else:  # type_text
        spec["text"] = expected
        spec["chars"] = len(expected) if expected else 0
    return {"challenge": spec, "lock_id": lock_id}


def complete_release(conn, lock_id: int, token: str,
                     response: str | None = None) -> dict:
    """Complete an early-release challenge.

    For wait friction, ``response`` is ignored — the elapsed time is what
    matters. For type_text friction, ``response`` must equal the random text
    that ``request_release`` returned.
    """
    _ensure_table(conn)
    lk = get(conn, lock_id)
    if not lk:
        return {"error": "not found"}
    if lk.get("released_at") is not None:
        return {"already_released": True}
    if lk.get("challenge_token") != token:
        return {"error": "invalid or missing challenge token"}
    friction = lk.get("friction") or {}
    started = lk.get("challenge_started_at") or 0
    if friction.get("type") == "wait":
        elapsed = time.time() - started
        needed = friction["seconds"]
        if elapsed < needed:
            return {"error": "wait period not yet elapsed",
                    "remaining_seconds": round(needed - elapsed, 1)}
    elif friction.get("type") == "type_text":
        if response != lk.get("challenge_expected"):
            return {"error": "incorrect text"}
    else:
        return {"error": "lock has no friction"}
    conn.execute("UPDATE locks SET released_at=? WHERE id=?",
                 (time.time(), lock_id))
    conn.commit()
    try:
        from . import audit
        audit.log(conn, "user", "lock.release", {
            "lock_id": lock_id, "kind": lk.get("kind"),
            "target": lk.get("target"),
            "method": "friction_completed",
        })
    except Exception:
        pass
    return {"released": True}


# --- Internal ---

def _row_to_dict(r) -> dict:
    d = dict(r)
    if d.get("friction"):
        try:
            d["friction"] = json.loads(d["friction"])
        except Exception:
            pass
    return d
