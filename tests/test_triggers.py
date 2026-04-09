"""Tests for the triggers module — engine, DSL, calls, worker."""
import json
import time
import pytest
from unittest.mock import patch

from sentinel import triggers, ai_store, blocker, db as db_mod


# --- CRUD ---

def test_create_and_get(conn):
    recipe = {"steps": [{"call": "now", "save_as": "t"}]}
    tid = triggers.create(conn, "test1", recipe, interval_sec=60, description="hi")
    assert tid > 0
    t = triggers.get(conn, "test1")
    assert t["name"] == "test1"
    assert t["interval_sec"] == 60
    assert t["description"] == "hi"
    assert t["enabled"] == 1
    assert t["recipe"] == recipe


def test_create_replaces_by_name(conn):
    triggers.create(conn, "x", {"steps": []}, interval_sec=60)
    triggers.create(conn, "x", {"steps": [{"call": "now", "save_as": "t"}]}, interval_sec=120)
    t = triggers.get(conn, "x")
    assert t["interval_sec"] == 120
    assert len(t["recipe"]["steps"]) == 1
    assert len(triggers.list_all(conn)) == 1


def test_list_and_delete(conn):
    triggers.create(conn, "a", {"steps": []}, interval_sec=60)
    triggers.create(conn, "b", {"steps": []}, interval_sec=60)
    assert len(triggers.list_all(conn)) == 2
    triggers.delete(conn, "a")
    assert len(triggers.list_all(conn)) == 1
    assert triggers.get(conn, "a") is None


def test_set_enabled(conn):
    triggers.create(conn, "z", {"steps": []}, interval_sec=60)
    triggers.set_enabled(conn, "z", False)
    assert triggers.get(conn, "z")["enabled"] == 0
    triggers.set_enabled(conn, "z", True)
    assert triggers.get(conn, "z")["enabled"] == 1


def test_create_validates_interval(conn):
    with pytest.raises(ValueError):
        triggers.create(conn, "bad", {"steps": []}, interval_sec=2)


def test_create_validates_recipe_shape(conn):
    with pytest.raises(ValueError):
        triggers.create(conn, "bad", {"not_steps": []}, interval_sec=60)
    with pytest.raises(ValueError):
        triggers.create(conn, "bad", {"steps": "not a list"}, interval_sec=60)


def test_create_rejects_unknown_call(conn):
    with pytest.raises(ValueError):
        triggers.create(conn, "bad",
                        {"steps": [{"call": "definitely_not_a_call"}]}, interval_sec=60)


def test_create_rejects_unknown_op(conn):
    recipe = {"steps": [{"when": {"var": "x", "op": "WAT", "value": 1}, "do": []}]}
    with pytest.raises(ValueError):
        triggers.create(conn, "bad", recipe, interval_sec=60)


def test_create_requires_name(conn):
    with pytest.raises(ValueError):
        triggers.create(conn, "", {"steps": []}, interval_sec=60)


# --- Path resolution ---

def test_resolve_path_dict():
    locals_d = {"a": {"b": {"c": 42}}}
    assert triggers._resolve_path(locals_d, "a.b.c") == 42
    assert triggers._resolve_path(locals_d, "a.b") == {"c": 42}
    assert triggers._resolve_path(locals_d, "a.missing") is None


def test_resolve_path_list_index():
    locals_d = {"items": [{"x": 1}, {"x": 2}]}
    assert triggers._resolve_path(locals_d, "items.1.x") == 2
    assert triggers._resolve_path(locals_d, "items.99.x") is None


def test_resolve_path_through_none():
    assert triggers._resolve_path({"a": None}, "a.b.c") is None


def test_resolve_top_level():
    assert triggers._resolve_path({"x": 5}, "x") == 5


# --- Template substitution ---

def test_substitute_string():
    assert triggers._substitute("hello ${name}", {"name": "world"}) == "hello world"


def test_substitute_whole_string_preserves_type():
    assert triggers._substitute("${n}", {"n": 42}) == 42
    assert triggers._substitute("${flag}", {"flag": True}) is True


def test_substitute_dict_recursive():
    out = triggers._substitute(
        {"domain": "${cur.domain}", "static": "yes"},
        {"cur": {"domain": "evil.com"}})
    assert out == {"domain": "evil.com", "static": "yes"}


def test_substitute_list_recursive():
    out = triggers._substitute(["a", "${x}", "b"], {"x": "MIDDLE"})
    assert out == ["a", "MIDDLE", "b"]


def test_substitute_passthrough():
    assert triggers._substitute(42, {}) == 42
    assert triggers._substitute(None, {}) is None
    assert triggers._substitute([1, 2], {}) == [1, 2]


def test_substitute_missing_var_in_string():
    # Missing template inside a larger string becomes empty
    assert triggers._substitute("x=${missing}", {}) == "x="


# --- Conditions ---

@pytest.mark.parametrize("op,val,expected,result", [
    ("equals", "a", "a", True),
    ("equals", "a", "b", False),
    ("not_equals", 1, 2, True),
    ("gt", 5, 3, True),
    ("gt", 3, 5, False),
    ("gte", 5, 5, True),
    ("lt", 1, 2, True),
    ("lte", 2, 2, True),
    ("in", "x", ["x", "y"], True),
    ("in", "z", ["x", "y"], False),
    ("contains", ["a", "b"], "a", True),
    ("contains", "hello world", "world", True),
    ("truthy", "x", None, True),
    ("truthy", "", None, False),
    ("truthy", 0, None, False),
    ("falsy", 0, None, True),
    ("falsy", "x", None, False),
])
def test_condition_ops(op, val, expected, result):
    cond = {"var": "v", "op": op, "value": expected}
    assert triggers._evaluate_condition(cond, {"v": val}) is result


def test_condition_handles_none():
    cond = {"var": "missing", "op": "gt", "value": 5}
    assert triggers._evaluate_condition(cond, {}) is False


def test_condition_handles_type_mismatch():
    cond = {"var": "x", "op": "gt", "value": 5}
    assert triggers._evaluate_condition(cond, {"x": "not a number"}) is False


# --- Execution ---

def test_run_once_simple(conn):
    recipe = {"steps": [{"call": "now", "save_as": "t"}]}
    triggers.create(conn, "t1", recipe, interval_sec=60)
    out = triggers.run_once(conn, "t1")
    assert out["status"] == "ok"
    assert "t" in out["locals"]
    assert "hour" in out["locals"]["t"]


def test_run_once_updates_last_run(conn):
    triggers.create(conn, "t2", {"steps": [{"call": "now", "save_as": "t"}]},
                    interval_sec=60)
    before = time.time()
    triggers.run_once(conn, "t2")
    t = triggers.get(conn, "t2")
    assert t["last_run"] >= before
    assert t["last_status"] == "ok"


def test_run_once_missing_trigger(conn):
    out = triggers.run_once(conn, "nonexistent")
    assert "error" in out


def test_run_once_executes_kv_chain(conn):
    recipe = {"steps": [
        {"call": "kv_set", "args": {"namespace": "tr:test", "key": "n", "value": 5}},
        {"call": "kv_get", "args": {"namespace": "tr:test", "key": "n"}, "save_as": "v"},
    ]}
    triggers.create(conn, "kv_chain", recipe, interval_sec=60)
    out = triggers.run_once(conn, "kv_chain")
    assert out["locals"]["v"] == 5


def test_run_once_increment(conn):
    recipe = {"steps": [
        {"call": "kv_increment", "args": {"namespace": "tr:c", "key": "n"}, "save_as": "n"},
        {"call": "kv_increment", "args": {"namespace": "tr:c", "key": "n"}, "save_as": "n2"},
    ]}
    triggers.create(conn, "incr", recipe, interval_sec=60)
    out = triggers.run_once(conn, "incr")
    assert out["locals"]["n"] == 1
    assert out["locals"]["n2"] == 2


def test_run_once_when_branch_taken(conn):
    recipe = {"steps": [
        {"call": "kv_set", "args": {"namespace": "tr:b", "key": "v", "value": "yes"}},
        {"when": {"var": "v", "op": "equals", "value": "yes"}, "do": [
            {"call": "kv_set", "args": {"namespace": "tr:b", "key": "branch", "value": "taken"}},
        ]},
    ]}
    # Manually preload the var that 'when' inspects (no save_as on first step)
    triggers.create(conn, "br1", {"steps": [
        {"call": "kv_get", "args": {"namespace": "tr:nope", "key": "x", "default": "yes"}, "save_as": "v"},
        {"when": {"var": "v", "op": "equals", "value": "yes"}, "do": [
            {"call": "kv_set", "args": {"namespace": "tr:b", "key": "branch", "value": "taken"}},
        ]},
    ]}, interval_sec=60)
    triggers.run_once(conn, "br1")
    assert ai_store.kv_get(conn, "tr:b", "branch") == "taken"


def test_run_once_when_branch_skipped(conn):
    triggers.create(conn, "br2", {"steps": [
        {"call": "kv_get", "args": {"namespace": "tr:nope", "key": "x", "default": "no"}, "save_as": "v"},
        {"when": {"var": "v", "op": "equals", "value": "yes"}, "do": [
            {"call": "kv_set", "args": {"namespace": "tr:b2", "key": "branch", "value": "taken"}},
        ]},
    ]}, interval_sec=60)
    triggers.run_once(conn, "br2")
    assert ai_store.kv_get(conn, "tr:b2", "branch") is None


def test_run_once_template_in_args(conn):
    triggers.create(conn, "tpl", {"steps": [
        {"call": "kv_set", "args": {"namespace": "tr:tpl", "key": "name", "value": "alice"}},
        {"call": "kv_get", "args": {"namespace": "tr:tpl", "key": "name"}, "save_as": "n"},
        {"call": "kv_set", "args": {"namespace": "tr:tpl", "key": "greeting",
                                    "value": "hello ${n}"}},
    ]}, interval_sec=60)
    triggers.run_once(conn, "tpl")
    assert ai_store.kv_get(conn, "tr:tpl", "greeting") == "hello alice"


def test_run_once_block_domain_via_template(conn):
    triggers.create(conn, "blk", {"steps": [
        {"call": "kv_set", "args": {"namespace": "tr:blk", "key": "d", "value": "evil.example"}},
        {"call": "kv_get", "args": {"namespace": "tr:blk", "key": "d"}, "save_as": "d"},
        {"call": "block_domain", "args": {"domain": "${d}"}, "save_as": "r"},
    ]}, interval_sec=60)
    with patch("sentinel.blocker._sync_hosts"):
        out = triggers.run_once(conn, "blk")
    assert out["locals"]["r"] == {"ok": True, "domain": "evil.example"}
    assert blocker.is_blocked_domain("evil.example")


def test_run_once_call_error_does_not_crash(conn):
    triggers.create(conn, "err", {"steps": [
        {"call": "block_domain", "args": {}, "save_as": "r"},  # missing domain
    ]}, interval_sec=60)
    out = triggers.run_once(conn, "err")
    assert out["status"] == "ok"
    assert out["locals"]["r"]["ok"] is False


def test_run_once_nested_conditions(conn):
    triggers.create(conn, "nest", {"steps": [
        {"call": "kv_set", "args": {"namespace": "tr:n", "key": "n", "value": 5}},
        {"call": "kv_get", "args": {"namespace": "tr:n", "key": "n"}, "save_as": "n"},
        {"when": {"var": "n", "op": "gte", "value": 3}, "do": [
            {"when": {"var": "n", "op": "lt", "value": 10}, "do": [
                {"call": "kv_set", "args": {"namespace": "tr:n", "key": "result", "value": "in_range"}},
            ]},
        ]},
    ]}, interval_sec=60)
    triggers.run_once(conn, "nest")
    assert ai_store.kv_get(conn, "tr:n", "result") == "in_range"


def test_run_once_log_call_writes_doc(conn):
    triggers.create(conn, "logger", {"steps": [
        {"call": "log", "args": {"message": "hello world"}},
    ]}, interval_sec=60)
    triggers.run_once(conn, "logger")
    docs = ai_store.doc_list(conn, namespace="trigger_log:logger")
    assert any(d["doc"]["message"] == "hello world" for d in docs)


def test_run_once_get_status(conn):
    triggers.create(conn, "st", {"steps": [
        {"call": "get_status", "save_as": "s"},
    ]}, interval_sec=60)
    out = triggers.run_once(conn, "st")
    assert "s" in out["locals"]
    assert "current" in out["locals"]["s"]
    assert "blocked" in out["locals"]["s"]


def test_vision_check_no_api_key(conn):
    triggers.create(conn, "vis", {"steps": [
        {"call": "vision_check", "args": {"user_context": "work"}, "save_as": "v"},
    ]}, interval_sec=60)
    out = triggers.run_once(conn, "vis")
    assert out["locals"]["v"]["verdict"] == "neutral"


# --- Due triggers ---

def test_due_triggers_respects_interval(conn):
    triggers.create(conn, "soon", {"steps": []}, interval_sec=60)
    # Just created, never run → due immediately
    assert any(t["name"] == "soon" for t in triggers.due_triggers(conn))
    # Mark as just-run
    conn.execute("UPDATE agent_triggers SET last_run=? WHERE name=?", (time.time(), "soon"))
    conn.commit()
    assert not any(t["name"] == "soon" for t in triggers.due_triggers(conn))


def test_due_triggers_skips_disabled(conn):
    triggers.create(conn, "off", {"steps": []}, interval_sec=60)
    triggers.set_enabled(conn, "off", False)
    assert not any(t["name"] == "off" for t in triggers.due_triggers(conn))


# --- Worker thread ---

def test_worker_start_stop(conn):
    triggers.start_worker(conn, tick_sec=0.1)
    assert triggers.is_worker_running()
    triggers.stop_worker()
    time.sleep(0.2)
    assert not triggers.is_worker_running()


def test_worker_runs_due_trigger(conn):
    triggers.create(conn, "wkr", {"steps": [
        {"call": "kv_increment", "args": {"namespace": "tr:wkr", "key": "n"}},
    ]}, interval_sec=5)
    triggers.start_worker(conn, tick_sec=0.05)
    try:
        # Wait briefly for the worker to pick it up
        deadline = time.time() + 2.0
        while time.time() < deadline:
            v = ai_store.kv_get(conn, "tr:wkr", "n", 0)
            if v >= 1:
                break
            time.sleep(0.05)
    finally:
        triggers.stop_worker()
    assert ai_store.kv_get(conn, "tr:wkr", "n", 0) >= 1


def test_worker_idempotent_start(conn):
    triggers.start_worker(conn, tick_sec=0.1)
    triggers.start_worker(conn, tick_sec=0.1)  # second call is no-op
    assert triggers.is_worker_running()
    triggers.stop_worker()


# --- list_calls ---

def test_list_calls_has_essentials():
    calls = triggers.list_calls()
    for k in ("vision_check", "get_status", "block_domain", "kv_set", "log", "now"):
        assert k in calls
    assert all(isinstance(v, str) and v for v in calls.values())


def test_call_registry_matches_descriptions():
    """Every CALL has a description, every description has a CALL."""
    assert set(triggers.CALLS.keys()) == set(triggers.list_calls().keys())


# --- Validation depth ---

def test_validate_recipe_rejects_deep_nesting(conn):
    # Build a 10-deep nested recipe
    recipe = {"steps": [{"when": {"var": "v", "op": "truthy"}, "do": []}]}
    inner = recipe["steps"][0]
    for _ in range(12):
        new = {"when": {"var": "v", "op": "truthy"}, "do": []}
        inner["do"] = [new]
        inner = new
    with pytest.raises(ValueError):
        triggers.create(conn, "deep", recipe, interval_sec=60)


# --- Author (LLM) — mocked ---

def test_author_from_text_parses_response():
    fake_response = json.dumps({
        "name": "test_auto",
        "interval_sec": 60,
        "description": "auto",
        "recipe": {"steps": [{"call": "now", "save_as": "t"}]},
    })

    async def fake_call_gemini(api_key, prompt, max_tokens=1500):
        return fake_response

    import asyncio
    with patch("sentinel.classifier.call_gemini", side_effect=fake_call_gemini):
        spec = asyncio.run(triggers.author_from_text("fake-key", "do something"))
    assert spec["name"] == "test_auto"
    assert spec["interval_sec"] == 60
    assert spec["recipe"]["steps"][0]["call"] == "now"


def test_author_from_text_strips_markdown_fences():
    fake_response = "```json\n" + json.dumps({
        "name": "fenced",
        "interval_sec": 60,
        "recipe": {"steps": [{"call": "now"}]},
    }) + "\n```"

    async def fake_call_gemini(api_key, prompt, max_tokens=1500):
        return fake_response

    import asyncio
    with patch("sentinel.classifier.call_gemini", side_effect=fake_call_gemini):
        spec = asyncio.run(triggers.author_from_text("fake-key", "x"))
    assert spec["name"] == "fenced"


def test_author_from_text_rejects_invalid_json():
    async def fake(api_key, prompt, max_tokens=1500):
        return "not valid json at all"

    import asyncio
    with patch("sentinel.classifier.call_gemini", side_effect=fake):
        with pytest.raises(ValueError, match="invalid JSON"):
            asyncio.run(triggers.author_from_text("k", "x"))


def test_author_from_text_rejects_missing_keys():
    async def fake(api_key, prompt, max_tokens=1500):
        return json.dumps({"name": "x"})  # missing interval_sec, recipe

    import asyncio
    with patch("sentinel.classifier.call_gemini", side_effect=fake):
        with pytest.raises(ValueError, match="missing keys"):
            asyncio.run(triggers.author_from_text("k", "x"))


def test_author_from_text_validates_recipe():
    async def fake(api_key, prompt, max_tokens=1500):
        return json.dumps({
            "name": "x",
            "interval_sec": 60,
            "recipe": {"steps": [{"call": "totally_fake_op"}]},
        })

    import asyncio
    with patch("sentinel.classifier.call_gemini", side_effect=fake):
        with pytest.raises(ValueError):
            asyncio.run(triggers.author_from_text("k", "x"))
