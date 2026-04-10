"""Append-only audit log — what the agent has been doing.

The current audit story has been "use ai_store.doc_add under namespace
agent_audit:*". Problem: any recipe can call doc_delete and erase its own
trail. Locks were the first half of "the agent can't undo a commitment";
this is the second half: "the agent can't undo its own paper trail."

Schema is dedicated and write-only via the public API:
- The only way to add a row is `audit.log()` (called by primitive
  implementations). The trigger DSL has no `audit_*` calls, so a
  recipe cannot insert.
- The only way to remove rows is `audit.cleanup_older_than()`, which
  refuses if any active `no_delete_audit` lock exists.
- There is no UPDATE.
- There is no payload storage. `args_summary` is a structured JSON dict
  with sanitized keys (numbers, type tags, fixed strings) — never raw
  values from primitives that read user data.

Every primitive that mutates state (block, unblock, lock create/release,
trigger CRUD, emergency exit, screen lock) calls `audit.log()` after the
operation. The user can `GET /audit` to review.

For tamper protection: the user can `create_lock(kind="no_delete_audit",
duration_seconds=...)` to make even themselves unable to wipe history
during a commitment period. This is the audit-level twin of the
`no_unblock_domain` lock kind.
"""
from __future__ import annotations

import json
import time


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY,
        ts REAL NOT NULL,
        actor TEXT NOT NULL,
        primitive TEXT NOT NULL,
        args_summary TEXT,
        result_status TEXT
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_ts ON audit_log(ts DESC)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_log_primitive ON audit_log(primitive)")


# --- Append (the only mutating operation) ---

def log(conn, actor: str, primitive: str, args: dict | None = None,
        status: str = "ok"):
    """Append a single audit row.

    Args are stored as a sanitized JSON summary, not the raw values.
    Callers should pass `args` containing only structured/typed fields
    they're comfortable persisting (e.g. {"domain": "twitter.com",
    "duration_seconds": 3600}). They should NOT pass content from
    primitives that read user data (HTTP body, SQL row text, iMessage
    text). The audit module does not enforce this — it's a contract.
    """
    _ensure_table(conn)
    args_json = json.dumps(args or {}, default=str)[:2000]
    conn.execute(
        "INSERT INTO audit_log (ts, actor, primitive, args_summary, result_status) "
        "VALUES (?, ?, ?, ?, ?)",
        (time.time(), actor, primitive, args_json, status))
    conn.commit()


# --- Read ---

def list_recent(conn, limit: int = 100, primitive: str | None = None,
                actor: str | None = None) -> list:
    _ensure_table(conn)
    q = "SELECT * FROM audit_log WHERE 1=1"
    params: list = []
    if primitive:
        q += " AND primitive = ?"
        params.append(primitive)
    if actor:
        q += " AND actor = ?"
        params.append(actor)
    q += " ORDER BY ts DESC LIMIT ?"
    params.append(int(limit))
    rows = conn.execute(q, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def count(conn, since: float | None = None) -> int:
    _ensure_table(conn)
    if since is not None:
        r = conn.execute(
            "SELECT COUNT(*) AS c FROM audit_log WHERE ts >= ?", (since,)).fetchone()
    else:
        r = conn.execute("SELECT COUNT(*) AS c FROM audit_log").fetchone()
    return r["c"]


# --- Cleanup (gated by no_delete_audit lock) ---

def cleanup_older_than(conn, cutoff_ts: float) -> dict:
    """Delete audit rows older than cutoff_ts.

    Refuses if any active no_delete_audit lock exists. Returns
    {"ok": True, "deleted": N} on success or {"ok": False, "reason": ...}.
    """
    _ensure_table(conn)
    # Lazy import — locks module imports nothing from audit
    from . import locks
    if locks.is_locked(conn, "no_delete_audit"):
        return {"ok": False, "reason": "no_delete_audit lock is active"}
    cur = conn.execute("DELETE FROM audit_log WHERE ts < ?", (cutoff_ts,))
    conn.commit()
    return {"ok": True, "deleted": cur.rowcount or 0}


def _row_to_dict(r) -> dict:
    d = dict(r)
    if d.get("args_summary"):
        try:
            d["args_summary"] = json.loads(d["args_summary"])
        except Exception:
            pass
    return d
