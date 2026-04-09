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

from . import db as db_mod, ai_store, blocker, monitor, stats as stats_mod, screenshots, scheduler

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


# --- CRUD ---

def create(conn, name: str, recipe: dict, interval_sec: int = 300, description: str = "") -> int:
    """Create or replace a trigger by name."""
    _ensure_table(conn)
    if not name or not isinstance(name, str):
        raise ValueError("name required")
    if interval_sec < 5:
        raise ValueError("interval_sec must be >= 5")
    if not isinstance(recipe, dict) or "steps" not in recipe:
        raise ValueError("recipe must be {steps: [...]}")
    validate_recipe(recipe)
    cur = conn.execute(
        "INSERT INTO agent_triggers (name, description, interval_sec, recipe, created_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(name) DO UPDATE SET description=excluded.description, "
        "interval_sec=excluded.interval_sec, recipe=excluded.recipe",
        (name, description, interval_sec, json.dumps(recipe), time.time()))
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


def delete(conn, name: str):
    _ensure_table(conn)
    conn.execute("DELETE FROM agent_triggers WHERE name=?", (name,))
    conn.commit()


def set_enabled(conn, name: str, enabled: bool):
    _ensure_table(conn)
    conn.execute("UPDATE agent_triggers SET enabled=? WHERE name=?", (1 if enabled else 0, name))
    conn.commit()


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
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
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
    blocker.unblock_domain(domain)
    return {"ok": True, "domain": domain}


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


def _call_start_focus(conn, args, ctx):
    return scheduler.start_focus_session(
        conn, int(args.get("duration_minutes", 60)), bool(args.get("locked", True)))


def _call_in_focus(conn, args, ctx):
    s = scheduler.get_focus_session(conn)
    return {"active": bool(s), "session": s}


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
    "start_focus": _call_start_focus,
    "in_focus": _call_in_focus,
}


def list_calls() -> dict:
    """For the LLM author: what calls exist, what they take, what they return."""
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
        "start_focus": "args:{duration_minutes?,locked?} → focus session dict",
        "in_focus": "args:{} → {active:bool, session:dict|null}",
    }


# --- Execution ---

def _execute_steps(conn, steps: list, locals_dict: dict, ctx: dict, depth: int = 0):
    if depth > 8:
        return
    for step in steps:
        if "when" in step:
            if not _evaluate_condition(step["when"], locals_dict):
                continue
            if "do" in step:
                _execute_steps(conn, step["do"], locals_dict, ctx, depth + 1)
                continue
        if "call" in step:
            fn = CALLS.get(step["call"])
            if not fn:
                continue
            args = _substitute(step.get("args", {}) or {}, locals_dict)
            try:
                result = fn(conn, args, ctx)
            except Exception as e:
                result = {"error": str(e)}
            save_as = step.get("save_as")
            if save_as:
                locals_dict[save_as] = result


def run_once(conn, name: str) -> dict:
    """Execute a trigger immediately. Returns step locals + status."""
    _ensure_table(conn)
    t = get(conn, name)
    if not t:
        return {"error": "not found"}
    locals_dict: dict = {}
    ctx = {"name": name, "trigger_id": t["id"]}
    status = "ok"
    err = None
    try:
        _execute_steps(conn, t["recipe"].get("steps", []), locals_dict, ctx)
    except Exception as e:
        status = "error"
        err = f"{type(e).__name__}: {e}"
        traceback.print_exc()
    conn.execute(
        "UPDATE agent_triggers SET last_run=?, last_status=?, last_result=? WHERE name=?",
        (time.time(), status if not err else err, json.dumps(locals_dict, default=str), name))
    conn.commit()
    return {"status": status, "error": err, "locals": locals_dict}


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
