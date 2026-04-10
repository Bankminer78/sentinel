"""Macros — named one-liners that desugar to primitive sub-recipes.

A macro is the bridge between "the agent should use generic primitives"
and "the user wants to write `vision_check` in one line, not 30 steps."

When the trigger validator sees a step like::

    {"call": "vision_check", "args": {"user_context": "deep work"}, "save_as": "snap"}

it expands the call into the canonical sub-recipe BEFORE the recipe is
stored. The expanded form is what runs and what `GET /triggers/{name}`
shows. The user can review every primitive call the macro emits — there
is no hidden execution path.

Built-in macros:

  vision_check(user_context) → screen_capture + http_fetch(gemini) +
    jsonpath(.candidates[0].content.parts[0].text)

  imessage_current() → sql_query against chat.db (the daemon's TCC-
    scoped path)

  imessage_recent_chats(limit) → sql_query, grouped
  imessage_recent_messages(handle, limit) → sql_query, filtered

The macros that have trust-boundary semantics (`notify`, `dialog`,
`block_domain`, `lock`, `emergency_exit`) are NOT macros. They stay as
typed primitives because the OS dialog must carry a daemon-enforced
"Sentinel is asking" label that recipe content cannot spoof.

User-authored macros:
  Stored in ai_store under namespace ``macros:{name}``. Loaded at
  validation time. The agent can write its own integrations (e.g., a
  Spotify check, a calendar query) once and reuse via a one-line call.
"""
from __future__ import annotations

import json
from typing import Callable

from . import ai_store


# ---------------------------------------------------------------------------
# Built-in macro implementations
# ---------------------------------------------------------------------------
#
# Each macro is a function: dict (the macro call's args) → list[dict]
# (the expanded steps to substitute in place of the macro call). The
# expansion may use ``save_as_prefix`` to scope its internal locals so it
# doesn't collide with the user's recipe variables.
#
# The validator passes the original `save_as` to the expansion so the
# macro's "final" output is bound to the user's chosen variable name.


CHAT_DB_PATH = "~/Library/Messages/chat.db"

# We hardcode the chat.db path here so the macro doesn't depend on the
# user adding chat.db to the sql_allowlist. The validator detects
# imessage_* macros and auto-adds chat.db to the allowlist on first use
# (with a flag the user can revoke). This keeps "imessage_current" a
# one-liner — the user shouldn't need to opt in to chat.db just to use
# the macro that we ship as built-in.

VISION_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-flash-latest:generateContent"
)

VISION_PROMPT = (
    "Look at this screenshot. Is the user doing productive work or "
    "getting distracted? Context: {user_context}. "
    'Respond with JSON: {{"verdict": "productive|distracted|neutral", '
    '"details": "brief description"}}'
)


def _expand_imessage_current(args: dict, save_as: str | None) -> list:
    """imessage_current() → sql_query + jsonpath to extract the row.

    Returns a 2-step expansion that calls sql_query against chat.db and
    binds the row[0] to the user's save_as variable.
    """
    sql = (
        "SELECT handle.id AS handle, handle.service AS service, "
        "chat.style AS style, message.text AS text, "
        "(message.date / 1000000000.0 + 978307200) AS ts "
        "FROM message "
        "JOIN chat_message_join cmj ON cmj.message_id = message.ROWID "
        "JOIN chat ON chat.ROWID = cmj.chat_id "
        "JOIN chat_handle_join chj ON chj.chat_id = chat.ROWID "
        "JOIN handle ON handle.ROWID = chj.handle_id "
        "WHERE message.text IS NOT NULL "
        "ORDER BY message.date DESC LIMIT 1"
    )
    sub = "_macro_imc"
    steps = [
        {"call": "sql_query", "args": {
            "db_path": CHAT_DB_PATH,
            "sql": sql,
            "params": [],
        }, "save_as": sub},
        {"call": "jsonpath", "args": {
            "value": "${" + sub + ".rows.0}",
            "path": "",
        }, "save_as": save_as or sub + "_out"},
    ]
    return steps


def _expand_imessage_recent_chats(args: dict, save_as: str | None) -> list:
    """imessage_recent_chats(limit) → sql_query grouped by handle."""
    limit = int(args.get("limit", 10))
    sql = (
        "SELECT handle.id AS handle, handle.service AS service, "
        "chat.style AS style, message.text AS text, "
        "MAX(message.date / 1000000000.0 + 978307200) AS ts "
        "FROM message "
        "JOIN chat_message_join cmj ON cmj.message_id = message.ROWID "
        "JOIN chat ON chat.ROWID = cmj.chat_id "
        "JOIN chat_handle_join chj ON chj.chat_id = chat.ROWID "
        "JOIN handle ON handle.ROWID = chj.handle_id "
        "WHERE message.text IS NOT NULL "
        "GROUP BY handle.id "
        "ORDER BY ts DESC LIMIT ?"
    )
    return [
        {"call": "sql_query", "args": {
            "db_path": CHAT_DB_PATH,
            "sql": sql,
            "params": [limit],
        }, "save_as": save_as or "_macro_irc"},
    ]


def _expand_imessage_recent_messages(args: dict, save_as: str | None) -> list:
    """imessage_recent_messages(handle, limit) → sql_query filtered."""
    handle = args.get("handle", "")
    limit = int(args.get("limit", 20))
    sql = (
        "SELECT message.text AS text, message.is_from_me AS from_me, "
        "(message.date / 1000000000.0 + 978307200) AS ts "
        "FROM message "
        "JOIN handle ON handle.ROWID = message.handle_id "
        "WHERE handle.id = ? AND message.text IS NOT NULL "
        "ORDER BY message.date DESC LIMIT ?"
    )
    return [
        {"call": "sql_query", "args": {
            "db_path": CHAT_DB_PATH,
            "sql": sql,
            "params": [handle, limit],
        }, "save_as": save_as or "_macro_irm"},
    ]


def _expand_vision_check(args: dict, save_as: str | None) -> list:
    """vision_check(user_context) → screen_capture + http_fetch + jsonpath.

    Final value bound to ``save_as`` is the parsed verdict text from
    Gemini's response. The Gemini API key is supplied via http_fetch's
    ``auth: gemini`` mechanism — the actual secret never enters the
    recipe's locals dict, audit log, or run history.
    """
    user_context = args.get("user_context", "general")
    prompt = VISION_PROMPT.format(user_context=user_context)
    final = save_as or "_macro_vc"
    return [
        {"call": "screen_capture", "save_as": "_macro_vc_cap"},
        {"call": "http_fetch", "args": {
            "method": "POST",
            "url": VISION_GEMINI_URL,
            "auth": "gemini",
            "headers": {"Content-Type": "application/json"},
            "body": {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {
                            "mime_type": "image/png",
                            "data": "${_macro_vc_cap.blob.base64}",
                        }},
                    ],
                }],
                "generationConfig": {
                    "maxOutputTokens": 200,
                    "temperature": 0,
                },
            },
        }, "save_as": "_macro_vc_resp"},
        {"call": "jsonpath", "args": {
            "value": "${_macro_vc_resp.json}",
            "path": "candidates.0.content.parts.0.text",
        }, "save_as": final},
    ]


# ---------------------------------------------------------------------------
# Macro registry
# ---------------------------------------------------------------------------

# Each entry is (name, expander_fn). The order of the registry is the
# order in which macros are checked during validation.
BUILTIN_MACROS: dict[str, Callable[[dict, str | None], list]] = {
    "imessage_current": _expand_imessage_current,
    "imessage_recent_chats": _expand_imessage_recent_chats,
    "imessage_recent_messages": _expand_imessage_recent_messages,
    "vision_check": _expand_vision_check,
}


def is_macro(call_name: str) -> bool:
    return call_name in BUILTIN_MACROS


def get_macro(call_name: str):
    return BUILTIN_MACROS.get(call_name)


# ---------------------------------------------------------------------------
# User-authored macros (loaded from ai_store)
# ---------------------------------------------------------------------------
#
# A user macro is stored as a doc under namespace "macros:{name}" with
# a doc body shape: {"steps": [...]}. When the validator encounters a
# call to a name that is not in BUILTIN_MACROS and not in CALLS, it
# checks the macro store. If found, the steps are inlined.
#
# User macros are scoped to the SAME save_as variable as a builtin macro:
# whatever variable name the call uses is bound to the LAST step's
# save_as in the inlined sub-recipe.


def get_user_macro(conn, name: str) -> list | None:
    """Look up a user-authored macro by name. Returns the steps list or None."""
    docs = ai_store.doc_list(conn, namespace=f"macros:{name}", limit=1)
    if not docs:
        return None
    doc = docs[0].get("doc") or {}
    if not isinstance(doc, dict):
        return None
    steps = doc.get("steps")
    if not isinstance(steps, list):
        return None
    return steps


def list_user_macros(conn) -> list:
    """All user-authored macros, by name."""
    namespaces = ai_store.doc_namespaces(conn)
    return [ns.removeprefix("macros:") for ns in namespaces if ns.startswith("macros:")]


def save_user_macro(conn, name: str, steps: list, description: str = ""):
    """Save a user-authored macro. Validation is the caller's responsibility."""
    if not name or not isinstance(name, str):
        raise ValueError("name required")
    if not isinstance(steps, list) or not steps:
        raise ValueError("steps must be a non-empty list")
    # Replace any existing version
    ai_store.doc_clear_namespace(conn, f"macros:{name}")
    ai_store.doc_add(conn, f"macros:{name}", {
        "name": name, "description": description, "steps": steps,
    })


# ---------------------------------------------------------------------------
# Recipe expansion (the validator calls this)
# ---------------------------------------------------------------------------


def expand_recipe(conn, recipe: dict, _depth: int = 0) -> dict:
    """Walk a recipe and inline every macro call.

    Returns a NEW recipe dict with macro calls replaced by their expanded
    sub-recipes. The original is not mutated. Recursive — a macro can
    contain a macro call (depth-limited).
    """
    if _depth > 4:
        raise ValueError("macro expansion depth exceeded")
    if not isinstance(recipe, dict):
        return recipe
    out = dict(recipe)
    if "steps" in out:
        out["steps"] = _expand_steps(conn, out["steps"], _depth)
    elif "do" in out:
        out["do"] = _expand_steps(conn, out["do"], _depth)
    return out


MAX_EXPANSION_DEPTH = 4


def _expand_steps(conn, steps: list, depth: int) -> list:
    if depth > MAX_EXPANSION_DEPTH:
        raise ValueError("macro expansion depth exceeded")
    if not isinstance(steps, list):
        return steps
    expanded = []
    for step in steps:
        if not isinstance(step, dict):
            expanded.append(step)
            continue
        # Conditional step — recurse into the do branch
        if "when" in step and "do" in step:
            new_step = dict(step)
            new_step["do"] = _expand_steps(conn, step["do"], depth + 1)
            expanded.append(new_step)
            continue
        # Call step — check if it's a macro
        if "call" in step:
            call_name = step["call"]
            macro_fn = BUILTIN_MACROS.get(call_name)
            if macro_fn is not None:
                sub = macro_fn(step.get("args") or {}, step.get("save_as"))
                # Recursively expand in case the macro itself uses macros
                sub = _expand_steps(conn, sub, depth + 1)
                expanded.extend(sub)
                continue
            # User-authored macro?
            user = get_user_macro(conn, call_name)
            if user is not None:
                sub = _expand_steps(conn, user, depth + 1)
                expanded.extend(sub)
                continue
        expanded.append(step)
    return expanded
