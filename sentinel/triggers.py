"""Triggers — the universal primitive for AI-authored features.

A trigger is a named recipe (steps + conditions) that runs on an interval.
The internal agent (Sentinel's own Gemini) translates plain English into a
trigger recipe and stores it. The worker thread runs due triggers.

This is what replaces shipped features. Instead of hardcoding "vision-based
focus enforcement", the user describes it in English, the internal agent
authors the trigger, Sentinel runs it forever.

Recipe DSL:
    {
      "steps": [
        {"call": "vision_check", "args": {"user_context": "deep work"}, "save_as": "snap"},
        {"call": "get_status", "save_as": "st"},
        {
          "when": {"var": "snap.verdict", "op": "equals", "value": "distracted"},
          "do": [
            {"call": "kv_increment", "args": {"namespace": "tr:focus", "key": "streak"}, "save_as": "n"},
            {
              "when": {"var": "n", "op": "gte", "value": 3},
              "do": [
                {"call": "block_domain", "args": {"domain": "${st.current.domain}"}},
                {"call": "kv_set", "args": {"namespace": "tr:focus", "key": "streak", "value": 0}}
              ]
            }
          ]
        }
      ]
    }

Templates: ``${var.path}`` resolves against accumulated step locals.
Conditions: ``{"var": "x.y", "op": "equals|gt|gte|lt|lte|in|contains|truthy|falsy", "value": ...}``
"""
from __future__ import annotations
import json, time, threading, asyncio, re, traceback
from typing import Any, Callable

from . import (
    db as db_mod, ai_store, blocker, monitor, stats as stats_mod,
    screenshots, locks as locks_mod, notify as notify_mod,
    imessage as imessage_mod, screen as screen_mod, emergency as emergency_mod,
    primitives as primitives_mod,
)

# --- Schema ---

def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS agent_triggers (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        description TEXT DEFAULT '',
        interval_sec INTEGER NOT NULL,
        recipe TEXT NOT NULL,
        enabled INTEGER DEFAULT 1,
        last_run REAL,
        last_status TEXT,
        last_result TEXT,
        created_at REAL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_triggers_enabled ON agent_triggers(enabled)")
    # Per-run history — capped to RUN_HISTORY_KEEP rows per trigger.
    conn.execute("""CREATE TABLE IF NOT EXISTS agent_trigger_runs (
        id INTEGER PRIMARY KEY,
        trigger_name TEXT NOT NULL,
        started_at REAL NOT NULL,
        duration_ms REAL,
        status TEXT,
        error TEXT,
        locals TEXT,
        steps TEXT
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_trigger_runs_name "
                 "ON agent_trigger_runs(trigger_name, started_at DESC)")


RUN_HISTORY_KEEP = 20  # rows per trigger


# --- CRUD ---

def create(conn, name: str, recipe: dict, interval_sec: int = 300, description: str = "") -> int:
    """Create or replace a trigger by name.

    Macros are expanded BEFORE validation, so the recipe stored in the
    table contains only primitive CALLs. The user-facing form (with the
    macros) is the input; the stored form (with the expanded sub-recipes)
    is what the user sees in GET /triggers/{name} — review-able.
    """
    _ensure_table(conn)
    if not name or not isinstance(name, str):
        raise ValueError("name required")
    if interval_sec < 5:
        raise ValueError("interval_sec must be >= 5")
    if not isinstance(recipe, dict) or "steps" not in recipe:
        raise ValueError("recipe must be {steps: [...]}")
    # Expand macros into their canonical primitive sub-recipes. Validation
    # then sees only known CALLs.
    from . import macros as macros_mod
    expanded = macros_mod.expand_recipe(conn, recipe)
    validate_recipe(expanded)
    cur = conn.execute(
        "INSERT INTO agent_triggers (name, description, interval_sec, recipe, created_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(name) DO UPDATE SET description=excluded.description, "
        "interval_sec=excluded.interval_sec, recipe=excluded.recipe",
        (name, description, interval_sec, json.dumps(expanded), time.time()))
    conn.commit()
    return cur.lastrowid or get(conn, name)["id"]


def get(conn, name: str) -> dict | None:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM agent_triggers WHERE name=?", (name,)).fetchone()
    return _row_to_dict(r) if r else None


def list_all(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute("SELECT * FROM agent_triggers ORDER BY created_at DESC").fetchall()
    return [_row_to_dict(r) for r in rows]


def delete(conn, name: str, force: bool = False, actor: str = "user") -> bool:
    """Delete a trigger. Returns False if a no_delete_trigger lock blocks it."""
    _ensure_table(conn)
    if not force:
        from . import locks
        if locks.is_locked(conn, "no_delete_trigger", name):
            _audit(conn, actor, "trigger.delete",
                   {"name": name, "force": False}, status="locked")
            return False
    conn.execute("DELETE FROM agent_triggers WHERE name=?", (name,))
    conn.commit()
    _audit(conn, actor, "trigger.delete",
           {"name": name, "force": force},
           status="forced" if force else "ok")
    return True


def set_enabled(conn, name: str, enabled: bool, force: bool = False,
                actor: str = "user") -> bool:
    """Toggle a trigger. Disabling is gated by no_disable_trigger locks."""
    _ensure_table(conn)
    if not enabled and not force:
        from . import locks
        if locks.is_locked(conn, "no_disable_trigger", name):
            _audit(conn, actor, "trigger.set_enabled",
                   {"name": name, "enabled": False}, status="locked")
            return False
    conn.execute("UPDATE agent_triggers SET enabled=? WHERE name=?",
                 (1 if enabled else 0, name))
    conn.commit()
    _audit(conn, actor, "trigger.set_enabled",
           {"name": name, "enabled": enabled, "force": force})
    return True


def _audit(conn, actor, primitive, args, status="ok"):
    """Best-effort audit log entry — never block the operation if it fails."""
    if conn is None:
        return
    try:
        from . import audit
        audit.log(conn, actor, primitive, args, status)
    except Exception:
        pass


def _row_to_dict(r) -> dict:
    d = dict(r)
    try:
        d["recipe"] = json.loads(d["recipe"])
    except Exception:
        d["recipe"] = {}
    if d.get("last_result"):
        try:
            d["last_result"] = json.loads(d["last_result"])
        except Exception:
            pass
    return d


# --- Validation ---

VALID_OPS = {"equals", "not_equals", "gt", "gte", "lt", "lte", "in", "contains", "truthy", "falsy"}


def validate_recipe(recipe: dict, _depth: int = 0):
    if _depth > 8:
        raise ValueError("recipe nesting too deep")
    steps = recipe.get("steps") if _depth == 0 else recipe.get("do", [])
    if not isinstance(steps, list):
        raise ValueError("steps must be a list")
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("each step must be a dict")
        if "when" in step:
            cond = step["when"]
            if not isinstance(cond, dict) or "op" not in cond or "var" not in cond:
                raise ValueError("'when' requires {var, op, value?}")
            if cond["op"] not in VALID_OPS:
                raise ValueError(f"unknown op: {cond['op']}")
            if "do" in step:
                validate_recipe({"do": step["do"]}, _depth + 1)
        if "call" in step:
            if step["call"] not in CALLS:
                raise ValueError(f"unknown call: {step['call']}")


# --- Template substitution ---

_TEMPLATE_RE = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_.]*)\}")


def _resolve_path(locals_dict: dict, path: str) -> Any:
    cur: Any = locals_dict
    parts = path.split(".")
    for i, part in enumerate(parts):
        if cur is None:
            return None
        # Special case: blob.base64 on a blob_ref dict — auto-encode the bytes.
        # The blob_ref's "_bytes" field is consumed here so the value is never
        # exposed as raw bytes to the recipe author.
        if part == "base64" and isinstance(cur, dict) and "_blob" in cur and "_bytes" in cur:
            from . import primitives as _p
            return _p.base64_encode(cur)
        if isinstance(cur, dict):
            # Hide the internal "_bytes" field from path traversal — only the
            # blob.base64 path can read the bytes.
            if part == "_bytes":
                return None
            cur = cur.get(part)
        elif isinstance(cur, (list, tuple)):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur


def _substitute(value: Any, locals_dict: dict) -> Any:
    if isinstance(value, str):
        # Whole-string substitution preserves type (e.g. ${n} -> int)
        m = _TEMPLATE_RE.fullmatch(value)
        if m:
            return _resolve_path(locals_dict, m.group(1))
        return _TEMPLATE_RE.sub(
            lambda mo: str(_resolve_path(locals_dict, mo.group(1)) or ""), value)
    if isinstance(value, dict):
        return {k: _substitute(v, locals_dict) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v, locals_dict) for v in value]
    return value


# --- Conditions ---

def _evaluate_condition(cond: dict, locals_dict: dict) -> bool:
    val = _resolve_path(locals_dict, cond["var"])
    op = cond["op"]
    expected = _substitute(cond.get("value"), locals_dict)
    try:
        if op == "equals":
            return val == expected
        if op == "not_equals":
            return val != expected
        if op == "gt":
            return val is not None and val > expected
        if op == "gte":
            return val is not None and val >= expected
        if op == "lt":
            return val is not None and val < expected
        if op == "lte":
            return val is not None and val <= expected
        if op == "in":
            return val in (expected or [])
        if op == "contains":
            return expected in (val or [])
        if op == "truthy":
            return bool(val)
        if op == "falsy":
            return not bool(val)
    except (TypeError, ValueError):
        return False
    return False


# --- Call registry: the abstract operations triggers can invoke. ---

def _call_vision_check(conn, args, ctx):
    api_key = db_mod.get_config(conn, "gemini_api_key")
    if not api_key:
        return {"verdict": "neutral", "details": "no api key"}
    user_context = args.get("user_context", "")
    return asyncio.run(screenshots.capture_and_analyze(api_key, user_context))


def _call_get_status(conn, args, ctx):
    return {
        "current": monitor.get_current(),
        "blocked": blocker.get_blocked(),
        "rules_count": len(db_mod.get_rules(conn, active_only=True)),
    }


def _call_get_current(conn, args, ctx):
    return monitor.get_current()


def _call_block_domain(conn, args, ctx):
    domain = args.get("domain", "").strip()
    if not domain:
        return {"ok": False, "reason": "no domain"}
    blocker.block_domain(domain)
    return {"ok": True, "domain": domain}


def _call_unblock_domain(conn, args, ctx):
    domain = args.get("domain", "").strip()
    if not domain:
        return {"ok": False, "reason": "no domain"}
    if not blocker.unblock_domain(domain, conn=conn):
        return {"ok": False, "reason": "locked"}
    return {"ok": True, "domain": domain}


def _call_create_lock(conn, args, ctx):
    name = args.get("name") or ctx.get("name") or "unnamed"
    kind = args.get("kind")
    target = args.get("target")
    duration = args.get("duration_seconds")
    friction = args.get("friction")
    if not kind or not duration:
        return {"ok": False, "reason": "kind and duration_seconds required"}
    try:
        lid = locks_mod.create(conn, name, kind, target, int(duration), friction)
        return {"ok": True, "id": lid, "kind": kind, "target": target}
    except ValueError as e:
        return {"ok": False, "reason": str(e)}


def _call_is_locked(conn, args, ctx):
    kind = args.get("kind")
    target = args.get("target")
    if not kind:
        return {"locked": False, "reason": "kind required"}
    return {"locked": locks_mod.is_locked(conn, kind, target)}


def _call_list_locks(conn, args, ctx):
    return locks_mod.list_active(conn, kind=args.get("kind"))


# --- iMessage sensor ---

def _call_imessage_current(conn, args, ctx):
    return imessage_mod.current_chat()


def _call_imessage_recent_chats(conn, args, ctx):
    return imessage_mod.recent_chats(limit=int(args.get("limit", 10)))


def _call_imessage_recent_messages(conn, args, ctx):
    return imessage_mod.recent_messages(
        args.get("handle", ""), limit=int(args.get("limit", 20)))


# --- Notify / dialog effectors ---

def _call_notify(conn, args, ctx):
    return notify_mod.notify(
        args.get("title", "Sentinel"),
        args.get("body", ""),
        args.get("subtitle", ""))


def _call_dialog(conn, args, ctx):
    return notify_mod.dialog(
        args.get("title", "Sentinel"),
        args.get("body", ""),
        buttons=args.get("buttons") or ["OK"],
        default_button=args.get("default_button"),
        timeout_seconds=args.get("timeout_seconds"))


# --- Screen lockout (Frozen Turkey) ---

def _call_lock_screen(conn, args, ctx):
    duration = args.get("duration_seconds")
    if not duration:
        return {"ok": False, "reason": "duration_seconds required"}
    try:
        s = screen_mod.lock(conn, int(duration), args.get("message", "Focus mode"))
        return {"ok": True, **s}
    except ValueError as e:
        return {"ok": False, "reason": str(e)}


def _call_is_screen_locked(conn, args, ctx):
    return screen_mod.get_state(conn)


# --- Emergency exit (read-only from triggers — agent can check, not spend) ---

def _call_emergency_remaining(conn, args, ctx):
    return emergency_mod.status(conn)


# --- Generic primitives (the agent's building blocks) ---

def _call_http_fetch(conn, args, ctx):
    return primitives_mod.http_fetch(
        conn,
        method=args.get("method", "GET"),
        url=args.get("url", ""),
        headers=args.get("headers"),
        body=args.get("body"),
        timeout=args.get("timeout", 30),
        auth=args.get("auth"),
        actor=f"trigger:{ctx.get('name', '?')}",
    )


def _call_sql_query(conn, args, ctx):
    return primitives_mod.sql_query(
        conn,
        db_path=args.get("db_path", ""),
        sql=args.get("sql", ""),
        params=args.get("params") or [],
        actor=f"trigger:{ctx.get('name', '?')}",
    )


def _call_jsonpath(conn, args, ctx):
    return primitives_mod.jsonpath(args.get("value"), args.get("path", ""))


def _call_screen_capture(conn, args, ctx):
    return primitives_mod.screen_capture(
        conn, actor=f"trigger:{ctx.get('name', '?')}")


def _call_regex_match(conn, args, ctx):
    return primitives_mod.regex_match(
        args.get("text", ""),
        args.get("pattern", ""),
        group=int(args.get("group", 0)))


def _call_base64_encode(conn, args, ctx):
    return {"value": primitives_mod.base64_encode(args.get("value"))}


def _call_get_score(conn, args, ctx):
    return {"score": stats_mod.calculate_score(conn)}


def _call_get_activities(conn, args, ctx):
    return db_mod.get_activities(
        conn, since=args.get("since"), limit=int(args.get("limit", 50)))


def _call_top_distractions(conn, args, ctx):
    return stats_mod.get_top_distractions(
        conn, days=int(args.get("days", 7)), limit=int(args.get("limit", 10)))


def _call_kv_get(conn, args, ctx):
    return ai_store.kv_get(conn, args["namespace"], args["key"], args.get("default"))


def _call_kv_set(conn, args, ctx):
    ai_store.kv_set(conn, args["namespace"], args["key"], args.get("value"))
    return {"ok": True}


def _call_kv_increment(conn, args, ctx):
    cur = ai_store.kv_get(conn, args["namespace"], args["key"], 0)
    if not isinstance(cur, (int, float)):
        cur = 0
    new = cur + args.get("delta", 1)
    ai_store.kv_set(conn, args["namespace"], args["key"], new)
    return new


def _call_doc_add(conn, args, ctx):
    doc_id = ai_store.doc_add(conn, args["namespace"], args["doc"], args.get("tags", []))
    return {"id": doc_id}


def _call_now(conn, args, ctx):
    from datetime import datetime
    now = datetime.now()
    return {
        "hour": now.hour, "minute": now.minute,
        "weekday": now.weekday(), "day": now.strftime("%A"),
        "ts": time.time(),
    }


def _call_log(conn, args, ctx):
    msg = str(args.get("message", ""))
    ai_store.doc_add(conn, f"trigger_log:{ctx['name']}",
                     {"message": msg, "ts": time.time()}, tags=["log"])
    return {"ok": True}


CALLS: dict[str, Callable] = {
    "vision_check": _call_vision_check,
    "get_status": _call_get_status,
    "get_current": _call_get_current,
    "block_domain": _call_block_domain,
    "unblock_domain": _call_unblock_domain,
    "get_score": _call_get_score,
    "get_activities": _call_get_activities,
    "top_distractions": _call_top_distractions,
    "kv_get": _call_kv_get,
    "kv_set": _call_kv_set,
    "kv_increment": _call_kv_increment,
    "doc_add": _call_doc_add,
    "now": _call_now,
    "log": _call_log,
    "create_lock": _call_create_lock,
    "is_locked": _call_is_locked,
    "list_locks": _call_list_locks,
    "imessage_current": _call_imessage_current,
    "imessage_recent_chats": _call_imessage_recent_chats,
    "imessage_recent_messages": _call_imessage_recent_messages,
    "notify": _call_notify,
    "dialog": _call_dialog,
    "lock_screen": _call_lock_screen,
    "is_screen_locked": _call_is_screen_locked,
    "emergency_remaining": _call_emergency_remaining,
    # Generic primitives — the agent's building blocks
    "http_fetch": _call_http_fetch,
    "sql_query": _call_sql_query,
    "jsonpath": _call_jsonpath,
    "screen_capture": _call_screen_capture,
    "regex_match": _call_regex_match,
    "base64_encode": _call_base64_encode,
}


def list_calls(include_macros: bool = True) -> dict:
    """For the LLM author: what calls exist, what they take, what they return.

    By default this includes both real CALLS (the primitives the runtime
    invokes directly) and macros (one-line shortcuts that desugar to a
    canonical primitive sub-recipe at validation time). The author should
    prefer the macro version when one exists — it's a one-liner and the
    expansion is reviewable in GET /triggers/{name}.
    """
    return {
        "vision_check": "args:{user_context} → {verdict:'productive'|'distracted'|'neutral', details:str}",
        "get_status": "args:{} → {current:{app,title,domain,url}, blocked:{domains:[...]}, rules_count:int}",
        "get_current": "args:{} → {app,title,domain,url,bundle_id}",
        "block_domain": "args:{domain} → {ok:bool, domain:str}",
        "unblock_domain": "args:{domain} → {ok:bool, domain:str}",
        "get_score": "args:{} → {score:float}  // 0-100 productivity score for today",
        "get_activities": "args:{limit?,since?} → [{app,title,domain,verdict,ts}, ...]",
        "top_distractions": "args:{days?,limit?} → [{domain,seconds}, ...]",
        "kv_get": "args:{namespace,key,default?} → the stored value (any type)",
        "kv_set": "args:{namespace,key,value} → {ok:true}",
        "kv_increment": "args:{namespace,key,delta?} → the new integer value (returned raw, not in a dict)",
        "doc_add": "args:{namespace,doc,tags?} → {id:int}",
        "now": "args:{} → {hour,minute,weekday,day:str,ts:float}",
        "log": "args:{message} → {ok:true}  // appends to trigger_log:{trigger_name}",
        "create_lock": (
            "args:{name?,kind,target?,duration_seconds,friction?} → {ok,id,kind,target}"
            "  // creates a commitment that nothing can undo before expiry."
            "  Built-in kinds: 'no_unblock_domain','no_unblock_app',"
            "'no_delete_trigger','no_disable_trigger'. Custom kinds work too —"
            " agent enforces those via is_locked checks."
            " friction examples: {type:'wait',seconds:600} or {type:'type_text',chars:200}"
        ),
        "is_locked": "args:{kind,target?} → {locked:bool}  // is any active lock matching this?",
        "list_locks": "args:{kind?} → [lock,...]  // active locks, optionally filtered by kind",
        "imessage_current": (
            "args:{} → {handle,service,is_group,last_message_ts,last_text} | {error}"
            "  // most recently active iMessage chat"
        ),
        "imessage_recent_chats": (
            "args:{limit?} → [{handle,service,is_group,last_message_ts,last_text},...]"
            "  // recent chat threads, newest first"
        ),
        "imessage_recent_messages": (
            "args:{handle,limit?} → [{ts,from_me,text},...]"
            "  // recent messages with a specific handle"
        ),
        "notify": (
            "args:{title,body,subtitle?} → {ok}"
            "  // macOS banner notification, non-blocking"
        ),
        "dialog": (
            "args:{title,body,buttons?,default_button?,timeout_seconds?} → {ok,button}"
            "  // modal popup, BLOCKS until clicked. Use for friction prompts"
        ),
        "lock_screen": (
            "args:{duration_seconds,message?} → {ok,active,until_ts,remaining_seconds}"
            "  // Frozen Turkey: full-screen lockout for the duration."
            " Cannot be ended early except by user emergency-exit"
        ),
        "is_screen_locked": (
            "args:{} → {active,until_ts,message,remaining_seconds}"
        ),
        "emergency_remaining": (
            "args:{} → {limit,used_this_month,remaining,month_start_ts}"
            "  // read-only — agent CANNOT trigger an exit, only the user can"
        ),
        # --- Generic primitives ---
        "http_fetch": (
            "args:{method,url,headers?,body?,timeout?} → {ok,status,headers,body_text,json?}"
            "  // HTTP request to an allowlisted host. Defaults: GET, 30s timeout."
            " On failure: {ok:false, reason_code: invalid_method|bad_url|host_not_allowed|"
            "ssrf_blocked|daemon_self_call|dns_failed|timeout|http_error|body_too_large}."
            " body can be a dict (auto-JSON) or a ${snap.base64} blob ref."
        ),
        "sql_query": (
            "args:{db_path,sql,params?} → {ok,rows,row_count}"
            "  // Read-only single-statement SQL against an allowlisted SQLite file."
            " Use ? placeholders + params list — never string-format user values into sql."
            " On failure: {ok:false, reason_code: path_not_allowed|multi_statement|"
            "sqlite_error|too_many_rows|bad_sql|bad_params}."
        ),
        "jsonpath": (
            "args:{value,path} → {ok,value} | {ok:false,reason_code:path_missing}"
            "  // Extract a nested value via dot/bracket path: 'foo.bar.0' or 'foo[0].bar'."
            " Use this on http_fetch.json to pull out specific fields."
        ),
        "screen_capture": (
            "args:{} → {ok, blob:{_blob,size,mime}} | {ok:false, reason_code}"
            "  // Take a screenshot. Returns a blob_ref the executor stores in locals."
            " Pass it to http_fetch via ${cap.blob.base64} (auto-base64-encodes the bytes)."
        ),
        "regex_match": (
            "args:{text,pattern,group?} → {ok,match} | {ok:false,reason_code}"
            "  // Single regex match. group=0 returns the full match."
        ),
        "base64_encode": (
            "args:{value} → {value:str}"
            "  // Base64-encode a string or a blob_ref's bytes."
        ),
    }


# --- Execution ---

def _step_status(result: Any) -> str:
    """Detect failure in a step's result. {error: ...} or {ok: false} → error."""
    if isinstance(result, dict):
        if "error" in result:
            return "error"
        if result.get("ok") is False:
            return "error"
    return "ok"


def _summarize(value: Any, max_len: int = 200) -> str:
    """Compact JSON of a value, truncated for run-log storage.

    Blob ``_bytes`` fields are replaced with a length tag before serializing
    so binary data never appears in the persisted run log or the audit
    trail. The summary is what the run-history debugger UI shows the user;
    it must be safe to render and store.
    """
    safe = _strip_blob_bytes(value)
    try:
        s = json.dumps(safe, default=str)
    except Exception:
        s = str(safe)
    return s if len(s) <= max_len else s[:max_len] + "…"


def _execute_steps(conn, steps: list, locals_dict: dict, ctx: dict,
                   depth: int = 0, run_log: list | None = None) -> list:
    """Run a list of steps, appending one entry per step to run_log.

    Each error entry carries an ``error_category`` (a fixed enum) so that
    sanitization for the LLM revise loop can be a clean field projection,
    not regex parsing of free-text error messages.
    """
    if run_log is None:
        run_log = []
    if depth > 8:
        run_log.append({"type": "error", "status": "error",
                        "error_category": "nested_too_deep"})
        return run_log
    for step in steps:
        if "when" in step:
            try:
                passed = _evaluate_condition(step["when"], locals_dict)
            except Exception as e:
                run_log.append({
                    "type": "when",
                    "var": step["when"].get("var"),
                    "op": step["when"].get("op"),
                    "status": "error",
                    "error_category": "condition_eval_failed",
                    "exception_type": type(e).__name__,
                })
                continue
            run_log.append({"type": "when", "var": step["when"].get("var"),
                            "op": step["when"].get("op"), "passed": passed,
                            "status": "ok"})
            if passed and "do" in step:
                _execute_steps(conn, step["do"], locals_dict, ctx, depth + 1, run_log)
            continue
        if "call" in step:
            call_name = step["call"]
            fn = CALLS.get(call_name)
            if not fn:
                run_log.append({
                    "type": "call", "call": call_name,
                    "status": "error", "error_category": "unknown_call",
                })
                continue
            try:
                args = _substitute(step.get("args", {}) or {}, locals_dict)
            except Exception as e:
                run_log.append({
                    "type": "call", "call": call_name,
                    "status": "error",
                    "error_category": "arg_substitution_failed",
                    "exception_type": type(e).__name__,
                })
                continue
            try:
                result = fn(conn, args, ctx)
                step_status = _step_status(result)
                # The `result` and `error` fields are kept for the run-history
                # debugger UI. The sanitization layer in
                # _sanitize_run_for_revise() drops both before they reach the
                # LLM — that's the prompt-injection defense.
                entry = {"type": "call", "call": call_name, "status": step_status,
                         "result": _summarize(result)}
                if step_status == "error":
                    entry["error_category"] = "step_returned_error"
                    if isinstance(result, dict):
                        entry["error"] = result.get("error") or result.get("reason") or "step returned ok=false"
                run_log.append(entry)
            except Exception as e:
                result = {"error": f"{type(e).__name__}: {e}"}
                run_log.append({
                    "type": "call", "call": call_name,
                    "status": "error",
                    "error_category": "step_raised",
                    "exception_type": type(e).__name__,
                    "error": result["error"],  # for run history; sanitization drops it
                })
            save_as = step.get("save_as")
            if save_as:
                locals_dict[save_as] = result
    return run_log


def _strip_blob_bytes(value):
    """Recursively replace blob_ref ``_bytes`` fields with a length tag.

    Used before any JSON serialization (audit, run history, revise prompt)
    so blob bytes never leak into persistent storage or the LLM.
    """
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k == "_bytes" and isinstance(v, (bytes, bytearray)):
                out["_bytes_len"] = len(v)
            else:
                out[k] = _strip_blob_bytes(v)
        return out
    if isinstance(value, list):
        return [_strip_blob_bytes(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_strip_blob_bytes(v) for v in value)
    return value


def _record_run(conn, name: str, started_at: float, duration_ms: float,
                status: str, error: str | None, locals_dict: dict, run_log: list):
    safe_locals = _strip_blob_bytes(locals_dict)
    safe_run_log = _strip_blob_bytes(run_log)
    conn.execute(
        "INSERT INTO agent_trigger_runs "
        "(trigger_name, started_at, duration_ms, status, error, locals, steps) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, started_at, duration_ms, status, error,
         json.dumps(safe_locals, default=str)[:5000],
         json.dumps(safe_run_log, default=str)[:5000]))
    # Trim to last RUN_HISTORY_KEEP rows for this trigger.
    conn.execute(
        "DELETE FROM agent_trigger_runs WHERE trigger_name=? AND id NOT IN "
        "(SELECT id FROM agent_trigger_runs WHERE trigger_name=? "
        " ORDER BY started_at DESC LIMIT ?)",
        (name, name, RUN_HISTORY_KEEP))
    conn.commit()


def run_once(conn, name: str) -> dict:
    """Execute a trigger immediately. Returns locals, step log, and status.

    Status is "ok" only if zero steps failed. A step fails if its call raised,
    returned ``{"error": ...}``, or returned ``{"ok": false, ...}``.
    """
    _ensure_table(conn)
    t = get(conn, name)
    if not t:
        return {"status": "error", "error": "not found", "locals": {}, "steps": []}
    locals_dict: dict = {}
    ctx = {"name": name, "trigger_id": t["id"]}
    started = time.time()
    fatal_err = None
    run_log: list = []
    try:
        run_log = _execute_steps(conn, t["recipe"].get("steps", []), locals_dict, ctx)
    except Exception as e:
        fatal_err = f"{type(e).__name__}: {e}"
        traceback.print_exc()
    duration_ms = (time.time() - started) * 1000
    failed_steps = [s for s in run_log if s.get("status") == "error"]
    if fatal_err:
        status = "error"
        error_msg = fatal_err
    elif failed_steps:
        status = "error"
        error_msg = (f"{len(failed_steps)} step(s) failed: " +
                     ", ".join(f"{s.get('call') or s.get('type')}({s.get('error','')})"
                               for s in failed_steps[:3]))
    else:
        status = "ok"
        error_msg = None
    _record_run(conn, name, started, duration_ms, status, error_msg, locals_dict, run_log)
    conn.execute(
        "UPDATE agent_triggers SET last_run=?, last_status=?, last_result=? WHERE name=?",
        (started, error_msg or "ok", json.dumps(locals_dict, default=str), name))
    conn.commit()
    return {
        "status": status,
        "error": error_msg,
        "locals": locals_dict,
        "steps": run_log,
        "failed_steps": [s.get("call") or s.get("type") for s in failed_steps],
        "duration_ms": duration_ms,
    }


def list_runs(conn, name: str, limit: int = 10) -> list:
    """Recent run history for a trigger, newest first."""
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM agent_trigger_runs WHERE trigger_name=? "
        "ORDER BY started_at DESC LIMIT ?",
        (name, limit)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("locals", "steps"):
            if d.get(k):
                try:
                    d[k] = json.loads(d[k])
                except Exception:
                    pass
        out.append(d)
    return out


def health(conn, name: str) -> dict:
    """Quick health summary: recent run counts, last error, last ok time."""
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT status, started_at, error FROM agent_trigger_runs "
        "WHERE trigger_name=? ORDER BY started_at DESC LIMIT ?",
        (name, RUN_HISTORY_KEEP)).fetchall()
    total = len(rows)
    failures = sum(1 for r in rows if r["status"] == "error")
    last_error = next((r["error"] for r in rows if r["status"] == "error"), None)
    last_ok_at = next((r["started_at"] for r in rows if r["status"] == "ok"), None)
    return {
        "name": name,
        "runs_recorded": total,
        "failures": failures,
        "success_rate": (total - failures) / total if total else None,
        "last_error": last_error,
        "last_ok_at": last_ok_at,
    }


def due_triggers(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM agent_triggers WHERE enabled=1").fetchall()
    now = time.time()
    out = []
    for r in rows:
        d = _row_to_dict(r)
        last = d.get("last_run") or 0
        if (now - last) >= d["interval_sec"]:
            out.append(d)
    return out


# --- Worker thread ---

_worker_thread: threading.Thread | None = None
_worker_running = False
_worker_lock = threading.Lock()


def start_worker(conn, tick_sec: float = 5.0):
    """Start the background worker that runs due triggers."""
    global _worker_thread, _worker_running
    with _worker_lock:
        if _worker_running:
            return
        _worker_running = True

        def loop():
            while _worker_running:
                try:
                    locks_mod.cleanup_expired(conn)
                    for t in due_triggers(conn):
                        if not _worker_running:
                            break
                        run_once(conn, t["name"])
                except Exception:
                    traceback.print_exc()
                # Sleep in small chunks so stop is responsive
                for _ in range(int(tick_sec * 10)):
                    if not _worker_running:
                        return
                    time.sleep(0.1)

        _worker_thread = threading.Thread(target=loop, daemon=True, name="trigger-worker")
        _worker_thread.start()


def stop_worker(timeout: float = 2.0):
    global _worker_running, _worker_thread
    with _worker_lock:
        _worker_running = False
        t = _worker_thread
        _worker_thread = None
    if t and t.is_alive():
        t.join(timeout=timeout)


def is_worker_running() -> bool:
    return _worker_running


# --- LLM author: natural language → recipe ---

AUTHOR_PROMPT = """You are Sentinel's internal agent. Translate the user's plain-English feature request into a JSON trigger recipe.

A trigger is a periodic task. The recipe is a list of "steps" — each step can call an operation, save its result, and conditionally execute child steps.

AVAILABLE OPERATIONS:
{calls}

DSL:
- step: {{"call": "op_name", "args": {{...}}, "save_as": "varname"}}
- condition: {{"when": {{"var": "name.path", "op": "equals|not_equals|gt|gte|lt|lte|in|contains|truthy|falsy", "value": ...}}, "do": [steps...]}}
- templates: use ${{varname.path}} inside string args to interpolate prior step results

Reply with ONLY a JSON object of this exact shape:
{{
  "name": "snake_case_unique_name",
  "interval_sec": <integer, minimum 5, typical 60-600>,
  "description": "<one sentence>",
  "recipe": {{"steps": [...]}}
}}

EXAMPLE — "every 5 min check vision; if distracted 3x in a row, block current domain":
{{
  "name": "vision_focus_enforcer",
  "interval_sec": 300,
  "description": "Block current domain when vision says distracted 3 times consecutively.",
  "recipe": {{
    "steps": [
      {{"call": "vision_check", "args": {{"user_context": "deep work"}}, "save_as": "snap"}},
      {{"call": "get_current", "save_as": "cur"}},
      {{"when": {{"var": "snap.verdict", "op": "equals", "value": "distracted"}},
        "do": [
          {{"call": "kv_increment", "args": {{"namespace": "tr:focus", "key": "streak"}}, "save_as": "n"}},
          {{"when": {{"var": "n", "op": "gte", "value": 3}},
            "do": [
              {{"call": "block_domain", "args": {{"domain": "${{cur.domain}}"}}}},
              {{"call": "kv_set", "args": {{"namespace": "tr:focus", "key": "streak", "value": 0}}}},
              {{"call": "log", "args": {{"message": "blocked ${{cur.domain}} after 3 distracted snapshots"}}}}
            ]
          }}
        ]
      }},
      {{"when": {{"var": "snap.verdict", "op": "equals", "value": "productive"}},
        "do": [{{"call": "kv_set", "args": {{"namespace": "tr:focus", "key": "streak", "value": 0}}}}]
      }}
    ]
  }}
}}

USER REQUEST: "{request}"

Return ONLY the JSON. No markdown, no explanation."""


async def author_from_text(api_key: str, request: str) -> dict:
    """Use Gemini to author a trigger recipe from a plain-English request."""
    from . import classifier
    calls_desc = "\n".join(f"- {k}: {v}" for k, v in list_calls().items())
    prompt = AUTHOR_PROMPT.format(calls=calls_desc, request=request)
    raw = await classifier.call_gemini(api_key, prompt, max_tokens=4000)
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}: {raw[:200]}")
    # Validate shape
    if not all(k in obj for k in ("name", "interval_sec", "recipe")):
        raise ValueError(f"LLM output missing keys: {obj}")
    validate_recipe(obj["recipe"])
    return obj


# --- Revise-loop sanitization (anti-prompt-injection) ---
#
# When a recipe fails, the daemon asks Gemini to author a fix. The failure
# context the LLM sees MUST NOT contain any payload data (HTTP body strings,
# SQL row contents, iMessage text, exception messages with embedded user
# input). Otherwise a malicious string anywhere downstream becomes a
# code-authoring channel: a prompt injection in an iMessage can rewrite the
# recipe to exfiltrate chat.db.
#
# Defense: every error entry in the run log carries an `error_category` (a
# fixed enum the executor sets at error-time) plus `exception_type` (a
# class name, never the message). The sanitization layer below builds the
# revise prompt from those structured fields only, plus a TYPE-ONLY
# skeleton of the locals dict (so the agent can see "this var has these
# keys" without seeing the values).

_LOCAL_SKELETON_MAX_DEPTH = 4
_LOCAL_SKELETON_MAX_LIST = 3


def _value_skeleton(value, depth: int = 0):
    """Return a payload-free type skeleton of a value.

    Strings/numbers/bools become their type tag. Dicts recurse with keys
    intact. Lists show their length and the skeleton of the first few
    elements. Bytes/blobs are summarized by length only.
    """
    if depth >= _LOCAL_SKELETON_MAX_DEPTH:
        return f"<{type(value).__name__}>"
    if value is None:
        return "<null>"
    if isinstance(value, bool):
        return "<bool>"
    if isinstance(value, int):
        return "<int>"
    if isinstance(value, float):
        return "<float>"
    if isinstance(value, str):
        return "<str>"
    if isinstance(value, bytes):
        return f"<bytes len={len(value)}>"
    if isinstance(value, dict):
        return {k: _value_skeleton(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        head = [_value_skeleton(v, depth + 1) for v in list(value)[:_LOCAL_SKELETON_MAX_LIST]]
        return {"<list>": head, "len": len(value)}
    return f"<{type(value).__name__}>"


# Fields that may carry user data — stripped before sanitization.
_PAYLOAD_FIELDS = {"result", "error"}


def _sanitize_step_entry(entry: dict) -> dict:
    """Project a run_log entry to its payload-free fields.

    Keeps: type, call, var, op, passed, status, error_category, exception_type.
    Drops: result (truncated payload), error (free-text message).
    """
    out = {}
    for k, v in entry.items():
        if k in _PAYLOAD_FIELDS:
            continue
        out[k] = v
    return out


def _sanitize_run_for_revise(run_log: list, locals_dict: dict,
                             fatal_error: str | None) -> dict:
    """Build the structured failure context the LLM sees on revise.

    Returns a dict with:
      - steps: payload-free per-step records
      - locals_skeleton: type skeleton of the final locals (no values)
      - fatal_error_type: class name of any fatal exception (never the message)
      - failed_step_count: how many steps were marked error
    """
    sanitized_steps = [_sanitize_step_entry(e) for e in (run_log or [])]
    failed = sum(1 for e in sanitized_steps if e.get("status") == "error")
    # fatal_error today is the human error_msg built in run_once. Strip it
    # to just the type name when it came from an exception, otherwise drop.
    fatal_type = None
    if fatal_error:
        # The format is "ExceptionType: message" — keep only the type.
        first = fatal_error.split(":", 1)[0].strip()
        if first and first.endswith("Error"):
            fatal_type = first
    return {
        "steps": sanitized_steps,
        "locals_skeleton": _value_skeleton(locals_dict or {}),
        "fatal_error_type": fatal_type,
        "failed_step_count": failed,
    }


REVISE_PROMPT = """You authored a recipe that failed when test-run. Fix it.

ORIGINAL USER REQUEST: "{request}"

PRIOR ATTEMPT (the recipe you wrote — which is structured JSON, not user data):
{prior_spec}

WHAT HAPPENED ON THE TEST RUN (sanitized — payloads have been stripped to
prevent prompt-injection from primitive return values; you see structure
only, not contents):

{sanitized}

Each step entry tells you: which call was made, whether it succeeded, and
on failure an `error_category` (one of: unknown_call, arg_substitution_failed,
step_returned_error, step_raised, condition_eval_failed, nested_too_deep)
plus an `exception_type` if the failure raised. The locals_skeleton shows
the SHAPE of each saved variable (its keys and value types) but never the
values themselves.

Common bug categories and what each implies:
- error_category=unknown_call: you used a call name that doesn't exist —
  pick one from the available operations below.
- error_category=arg_substitution_failed: a ${{var.path}} template referenced
  a path that didn't resolve. Check the locals_skeleton for the actual keys.
- error_category=step_returned_error: the call ran but its preconditions
  weren't met (e.g. a required arg was empty/missing). Check the call's
  args against the shape spec below.
- error_category=step_raised: the call's implementation raised an exception
  (exception_type tells you which class). Usually an arg shape mismatch.
- error_category=condition_eval_failed: a `when` clause's var/op/value
  combination couldn't be evaluated.
- A successful step with status=ok but a `when` clause whose passed=false
  is not a failure — it just means the branch didn't fire. Fix this only
  if the branch SHOULD have fired.

AVAILABLE OPERATIONS (with shapes):
{calls}

DSL reminder:
- step: {{"call": "op_name", "args": {{...}}, "save_as": "varname"}}
- condition: {{"when": {{"var": "name.path", "op": "equals|not_equals|gt|gte|lt|lte|in|contains|truthy|falsy", "value": ...}}, "do": [steps...]}}
- templates: ${{varname.path}} inside string args interpolates prior step results

Return ONLY a corrected JSON object of the same shape:
{{
  "name": "snake_case_unique_name",
  "interval_sec": <int>,
  "description": "<one sentence>",
  "recipe": {{"steps": [...]}}
}}
No markdown, no explanation."""


async def _revise_from_failure(api_key: str, request: str, prior_spec: dict | None,
                               failure: dict) -> dict:
    """Ask the LLM to fix a recipe given a sanitized failure record.

    The failure dict carries `steps` (raw run log), `locals` (raw values),
    and `error` (free-text). All three are passed through
    _sanitize_run_for_revise() before being interpolated into the prompt.
    The LLM never sees raw payload content from primitive return values.
    """
    from . import classifier
    calls_desc = "\n".join(f"- {k}: {v}" for k, v in list_calls().items())
    sanitized = _sanitize_run_for_revise(
        failure.get("steps", []),
        failure.get("locals", {}),
        failure.get("error"),
    )
    prompt = REVISE_PROMPT.format(
        request=request,
        prior_spec=json.dumps(prior_spec or {}, default=str)[:2000],
        sanitized=json.dumps(sanitized, indent=2)[:3000],
        calls=calls_desc,
    )
    raw = await classifier.call_gemini(api_key, prompt, max_tokens=4000)
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    obj = json.loads(raw)
    if not all(k in obj for k in ("name", "interval_sec", "recipe")):
        raise ValueError(f"revision missing keys: {obj}")
    validate_recipe(obj["recipe"])
    return obj


async def author_and_test(conn, api_key: str, request: str,
                          max_revisions: int = 2) -> dict:
    """Author → test-run → revise loop. Returns the working trigger or fails.

    Failure feedback works for every phase the agent might botch:
    - LLM returns invalid JSON or wrong shape
    - validate_recipe rejects an unknown call / op / depth
    - create() rejects (e.g. interval too low, name empty)
    - run_once detects a step that returned ok=false or raised
    """
    history = []
    spec: dict | None = None
    last_failure: dict | None = None
    last_run: dict | None = None

    for attempt in range(max_revisions + 1):
        # Author or revise
        try:
            if attempt == 0:
                spec = await author_from_text(api_key, request)
            else:
                spec = await _revise_from_failure(api_key, request, spec, last_failure or {})
        except (ValueError, json.JSONDecodeError) as e:
            last_failure = {"phase": "author", "status": "error", "error": str(e)}
            history.append({"attempt": attempt, **last_failure})
            continue

        # Persist
        try:
            create(conn, spec["name"], spec["recipe"],
                   interval_sec=int(spec.get("interval_sec", 300)),
                   description=spec.get("description", ""))
        except ValueError as e:
            last_failure = {"phase": "create", "status": "error",
                            "error": str(e), "prior_spec": spec}
            history.append({"attempt": attempt, "phase": "create",
                            "status": "error", "error": str(e),
                            "spec_name": spec.get("name")})
            continue

        # Test-run
        last_run = run_once(conn, spec["name"])
        history.append({
            "attempt": attempt, "phase": "run", "status": last_run["status"],
            "error": last_run.get("error"),
            "spec_name": spec.get("name"),
        })

        if last_run["status"] == "ok":
            return {
                "ok": True, "spec": spec, "test_run": last_run,
                "attempts": attempt + 1, "history": history,
            }

        # Run failed — capture full diagnostics for the next revision
        last_failure = {
            "phase": "run", "status": "error",
            "error": last_run.get("error"),
            "steps": last_run.get("steps", []),
            "locals": last_run.get("locals", {}),
        }
        # Delete this draft unless it's our last shot
        if attempt < max_revisions:
            delete(conn, spec["name"])

    return {
        "ok": False, "spec": spec, "test_run": last_run,
        "attempts": max_revisions + 1, "history": history,
        "error": (last_failure or {}).get("error") or "all attempts failed",
    }
