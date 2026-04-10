"""Tests for sentinel.macros — recipe expansion at validation time.

A macro is a one-line call in the DSL that the validator replaces with a
canonical sub-recipe BEFORE the recipe is stored. The expanded form is
what runs and what the user reviews. This file verifies expansion is
correct, recursive, and survives the round-trip through triggers.create.
"""
import json
from unittest.mock import patch, MagicMock
import pytest

from sentinel import macros, triggers, ai_store, db, sandbox


# ---------------------------------------------------------------------------
# Macro registry
# ---------------------------------------------------------------------------


def test_builtin_macros_registered():
    assert macros.is_macro("vision_check")
    assert macros.is_macro("imessage_current")
    assert macros.is_macro("imessage_recent_chats")
    assert macros.is_macro("imessage_recent_messages")


def test_unknown_call_not_a_macro():
    assert not macros.is_macro("definitely_not_a_macro")
    assert not macros.is_macro("notify")  # trusted primitive, not a macro
    assert not macros.is_macro("dialog")
    assert not macros.is_macro("block_domain")


# ---------------------------------------------------------------------------
# Basic expansion
# ---------------------------------------------------------------------------


def test_imessage_current_expands_to_sql_query(conn):
    recipe = {"steps": [
        {"call": "imessage_current", "save_as": "chat"},
    ]}
    out = macros.expand_recipe(conn, recipe)
    call_names = [s.get("call") for s in out["steps"]]
    assert "imessage_current" not in call_names
    assert "sql_query" in call_names


def test_imessage_current_uses_chat_db_path(conn):
    recipe = {"steps": [{"call": "imessage_current", "save_as": "x"}]}
    out = macros.expand_recipe(conn, recipe)
    sql_step = next(s for s in out["steps"] if s.get("call") == "sql_query")
    assert "chat.db" in sql_step["args"]["db_path"]
    assert "message" in sql_step["args"]["sql"].lower()


def test_imessage_recent_chats_passes_limit(conn):
    recipe = {"steps": [
        {"call": "imessage_recent_chats", "args": {"limit": 5}, "save_as": "c"},
    ]}
    out = macros.expand_recipe(conn, recipe)
    sql_step = next(s for s in out["steps"] if s.get("call") == "sql_query")
    assert sql_step["args"]["params"] == [5]


def test_imessage_recent_messages_passes_handle(conn):
    recipe = {"steps": [
        {"call": "imessage_recent_messages",
         "args": {"handle": "+15551234567", "limit": 20}, "save_as": "m"},
    ]}
    out = macros.expand_recipe(conn, recipe)
    sql_step = next(s for s in out["steps"] if s.get("call") == "sql_query")
    assert sql_step["args"]["params"] == ["+15551234567", 20]


def test_vision_check_expands_to_screen_capture_http_fetch_jsonpath(conn):
    recipe = {"steps": [
        {"call": "vision_check", "args": {"user_context": "deep work"},
         "save_as": "snap"},
    ]}
    out = macros.expand_recipe(conn, recipe)
    call_names = [s.get("call") for s in out["steps"]]
    assert "vision_check" not in call_names
    assert call_names == ["screen_capture", "http_fetch", "jsonpath"]


def test_vision_check_uses_gemini_auth(conn):
    recipe = {"steps": [
        {"call": "vision_check", "args": {"user_context": "work"}, "save_as": "v"},
    ]}
    out = macros.expand_recipe(conn, recipe)
    fetch_step = next(s for s in out["steps"] if s.get("call") == "http_fetch")
    assert fetch_step["args"]["auth"] == "gemini"
    assert "key=" not in fetch_step["args"]["url"]  # no key in URL


def test_vision_check_user_context_in_prompt(conn):
    recipe = {"steps": [
        {"call": "vision_check", "args": {"user_context": "writing a paper"},
         "save_as": "v"},
    ]}
    out = macros.expand_recipe(conn, recipe)
    fetch_step = next(s for s in out["steps"] if s.get("call") == "http_fetch")
    body = fetch_step["args"]["body"]
    text = body["contents"][0]["parts"][0]["text"]
    assert "writing a paper" in text


def test_vision_check_passes_blob_via_template(conn):
    recipe = {"steps": [
        {"call": "vision_check", "args": {"user_context": "x"}, "save_as": "v"},
    ]}
    out = macros.expand_recipe(conn, recipe)
    fetch_step = next(s for s in out["steps"] if s.get("call") == "http_fetch")
    body = fetch_step["args"]["body"]
    inline = body["contents"][0]["parts"][1]["inline_data"]
    assert "${" in inline["data"]
    assert ".blob.base64" in inline["data"]


def test_vision_check_save_as_binds_final_step(conn):
    recipe = {"steps": [
        {"call": "vision_check", "args": {"user_context": "x"}, "save_as": "verdict"},
    ]}
    out = macros.expand_recipe(conn, recipe)
    last = out["steps"][-1]
    assert last["save_as"] == "verdict"


# ---------------------------------------------------------------------------
# Conditional + nested expansion
# ---------------------------------------------------------------------------


def test_macro_inside_when_branch_expands(conn):
    recipe = {"steps": [
        {"call": "kv_set", "args": {"namespace": "x", "key": "k", "value": 1}},
        {"when": {"var": "x", "op": "truthy"}, "do": [
            {"call": "imessage_current", "save_as": "c"},
        ]},
    ]}
    out = macros.expand_recipe(conn, recipe)
    when_step = out["steps"][1]
    assert "imessage_current" not in [s.get("call") for s in when_step["do"]]
    assert "sql_query" in [s.get("call") for s in when_step["do"]]


def test_non_macro_calls_passthrough(conn):
    recipe = {"steps": [
        {"call": "block_domain", "args": {"domain": "x.com"}},
        {"call": "now", "save_as": "t"},
    ]}
    out = macros.expand_recipe(conn, recipe)
    # No expansion for non-macro calls
    assert [s["call"] for s in out["steps"]] == ["block_domain", "now"]


def test_expansion_does_not_mutate_original(conn):
    recipe = {"steps": [{"call": "imessage_current", "save_as": "x"}]}
    original_steps = list(recipe["steps"])
    macros.expand_recipe(conn, recipe)
    assert recipe["steps"] == original_steps


# ---------------------------------------------------------------------------
# Round-trip through triggers.create
# ---------------------------------------------------------------------------


def test_create_stores_expanded_recipe(conn):
    triggers.create(conn, "im_test", {"steps": [
        {"call": "imessage_current", "save_as": "chat"},
    ]}, interval_sec=60)
    stored = triggers.get(conn, "im_test")
    call_names = [s.get("call") for s in stored["recipe"]["steps"]]
    assert "imessage_current" not in call_names
    assert "sql_query" in call_names


def test_create_validates_expanded_form(conn):
    """The validator runs on the expanded recipe — primitive calls only."""
    # vision_check after expansion uses screen_capture, http_fetch, jsonpath
    # — all real CALLs. This should validate successfully.
    triggers.create(conn, "vis_test", {"steps": [
        {"call": "vision_check", "args": {"user_context": "x"}, "save_as": "v"},
    ]}, interval_sec=60)
    assert triggers.get(conn, "vis_test") is not None


def test_create_rejects_unknown_macro(conn):
    """A call name that is neither a primitive CALL nor a macro is rejected."""
    with pytest.raises(ValueError, match="unknown call"):
        triggers.create(conn, "bad", {"steps": [
            {"call": "definitely_not_a_thing"},
        ]}, interval_sec=60)


# ---------------------------------------------------------------------------
# User-authored macros
# ---------------------------------------------------------------------------


def test_save_user_macro(conn):
    macros.save_user_macro(conn, "my_macro", [
        {"call": "now", "save_as": "t"},
        {"call": "log", "args": {"message": "tick"}},
    ], description="my custom macro")
    out = macros.get_user_macro(conn, "my_macro")
    assert out is not None
    assert len(out) == 2
    assert out[0]["call"] == "now"


def test_user_macro_expanded_in_recipe(conn):
    macros.save_user_macro(conn, "log_now", [
        {"call": "now", "save_as": "_t"},
        {"call": "log", "args": {"message": "tick at ${_t.day}"}},
    ])
    recipe = {"steps": [
        {"call": "log_now"},
        {"call": "block_domain", "args": {"domain": "x.com"}},
    ]}
    out = macros.expand_recipe(conn, recipe)
    call_names = [s.get("call") for s in out["steps"]]
    # The user macro expanded into its 2 steps
    assert call_names == ["now", "log", "block_domain"]


def test_list_user_macros(conn):
    macros.save_user_macro(conn, "a", [{"call": "now"}])
    macros.save_user_macro(conn, "b", [{"call": "now"}])
    out = macros.list_user_macros(conn)
    assert "a" in out
    assert "b" in out


def test_save_user_macro_replaces_existing(conn):
    macros.save_user_macro(conn, "x", [{"call": "now"}])
    macros.save_user_macro(conn, "x", [
        {"call": "now"}, {"call": "log", "args": {"message": "v2"}}])
    out = macros.get_user_macro(conn, "x")
    assert len(out) == 2


def test_save_user_macro_rejects_empty(conn):
    with pytest.raises(ValueError):
        macros.save_user_macro(conn, "x", [])


def test_save_user_macro_rejects_no_name(conn):
    with pytest.raises(ValueError):
        macros.save_user_macro(conn, "", [{"call": "now"}])


def test_get_user_macro_missing(conn):
    assert macros.get_user_macro(conn, "nonexistent") is None


# ---------------------------------------------------------------------------
# Expansion depth limit (anti-recursion)
# ---------------------------------------------------------------------------


def test_recursive_macro_depth_limited(conn):
    """A user macro that contains itself eventually hits the depth cap."""
    macros.save_user_macro(conn, "recursive", [
        {"call": "recursive"},  # calls itself
    ])
    with pytest.raises(ValueError, match="depth"):
        macros.expand_recipe(conn, {"steps": [{"call": "recursive"}]})


# ---------------------------------------------------------------------------
# End-to-end: imessage_current macro runs against real chat.db (mocked)
# ---------------------------------------------------------------------------


def test_imessage_macro_runs_via_sql_query(conn, tmp_path):
    """The macro expands to sql_query which then needs the chat.db on the
    sql allowlist. Verify the path: macro → expansion → sql_query → row."""
    import sqlite3 as _sql
    fake_chat = tmp_path / "fake_chat.db"
    c = _sql.connect(str(fake_chat))
    c.executescript("""
        CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT, service TEXT);
        CREATE TABLE chat (ROWID INTEGER PRIMARY KEY, style INTEGER);
        CREATE TABLE message (ROWID INTEGER PRIMARY KEY, text TEXT,
                              handle_id INTEGER, is_from_me INTEGER, date INTEGER);
        CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
        CREATE TABLE chat_handle_join (chat_id INTEGER, handle_id INTEGER);
        INSERT INTO handle VALUES (1, '+15551234567', 'iMessage');
        INSERT INTO chat VALUES (1, 45);
        INSERT INTO message (text, handle_id, is_from_me, date)
          VALUES ('hello world', 1, 0, 9999999999);
        INSERT INTO chat_message_join VALUES (1, 1);
        INSERT INTO chat_handle_join VALUES (1, 1);
    """)
    c.commit()
    c.close()
    sandbox.set_sql_allowlist(conn, [str(fake_chat)])
    # Override the macro's chat.db path for this test
    with patch.object(macros, "CHAT_DB_PATH", str(fake_chat)):
        triggers.create(conn, "im_real", {"steps": [
            {"call": "imessage_current", "save_as": "chat"},
        ]}, interval_sec=60)
        out = triggers.run_once(conn, "im_real")
    assert out["status"] == "ok"
    # The jsonpath step extracts row[0] from sql_query.rows
    chat = out["locals"]["chat"]
    assert chat["ok"] is True
    assert chat["value"]["text"] == "hello world"
