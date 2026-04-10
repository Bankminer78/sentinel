"""Tests for the revise-loop sanitization (anti-prompt-injection).

The contract: when a recipe fails, the failure context the LLM sees during
the revise loop must NOT contain any payload data — no HTTP body strings,
no SQL row contents, no iMessage text, no exception messages with embedded
user input. Only structured fields the executor sets at error-time
(error_category, exception_type) plus a TYPE-ONLY skeleton of locals.

If a primitive ever returns a value containing INJECTION_CANARY and that
canary appears in the revise prompt, the test fails. This is the anti-
prompt-injection guarantee.
"""
import asyncio
import json
from unittest.mock import patch
import pytest

from sentinel import triggers


CANARY = "INJECTION_CANARY_PAYLOAD_FROM_USER_DATA"


# ---------------------------------------------------------------------------
# _value_skeleton: type-only projection of values
# ---------------------------------------------------------------------------


def test_skeleton_strings_become_type_tag():
    assert triggers._value_skeleton("any user data") == "<str>"
    assert triggers._value_skeleton(CANARY) == "<str>"


def test_skeleton_numbers():
    assert triggers._value_skeleton(42) == "<int>"
    assert triggers._value_skeleton(3.14) == "<float>"
    assert triggers._value_skeleton(True) == "<bool>"
    assert triggers._value_skeleton(None) == "<null>"


def test_skeleton_dict_preserves_keys_drops_values():
    sk = triggers._value_skeleton({"app": "Cursor", "domain": CANARY, "id": 5})
    assert sk == {"app": "<str>", "domain": "<str>", "id": "<int>"}
    # Critical: the canary string is NOT anywhere in the skeleton
    assert CANARY not in json.dumps(sk)


def test_skeleton_nested_dict():
    sk = triggers._value_skeleton({"snap": {"verdict": "distracted", "details": CANARY}})
    assert sk == {"snap": {"verdict": "<str>", "details": "<str>"}}
    assert CANARY not in json.dumps(sk)


def test_skeleton_list_shows_length_not_contents():
    sk = triggers._value_skeleton([CANARY, "another", "third"])
    assert sk["len"] == 3
    assert sk["<list>"] == ["<str>", "<str>", "<str>"]
    assert CANARY not in json.dumps(sk)


def test_skeleton_max_depth_truncates():
    deep = {"a": {"b": {"c": {"d": {"e": {"f": CANARY}}}}}}
    sk = triggers._value_skeleton(deep)
    s = json.dumps(sk)
    assert CANARY not in s


def test_skeleton_bytes_summary():
    sk = triggers._value_skeleton(b"some binary data here")
    assert sk == "<bytes len=21>"


# ---------------------------------------------------------------------------
# _sanitize_step_entry: drop result + error fields
# ---------------------------------------------------------------------------


def test_sanitize_step_drops_result_field():
    entry = {
        "type": "call", "call": "vision_check", "status": "ok",
        "result": f'{{"verdict": "distracted", "details": "{CANARY}"}}',
    }
    out = triggers._sanitize_step_entry(entry)
    assert "result" not in out
    assert CANARY not in json.dumps(out)


def test_sanitize_step_drops_error_field():
    entry = {
        "type": "call", "call": "block_domain", "status": "error",
        "error_category": "step_returned_error",
        "error": f"the user data {CANARY} caused this",
    }
    out = triggers._sanitize_step_entry(entry)
    assert "error" not in out
    assert out["error_category"] == "step_returned_error"
    assert CANARY not in json.dumps(out)


def test_sanitize_step_keeps_safe_fields():
    entry = {
        "type": "call", "call": "block_domain", "status": "error",
        "error_category": "step_returned_error",
        "exception_type": "ValueError",
        "result": "<unsafe>",
        "error": "<unsafe>",
    }
    out = triggers._sanitize_step_entry(entry)
    assert out == {
        "type": "call", "call": "block_domain", "status": "error",
        "error_category": "step_returned_error",
        "exception_type": "ValueError",
    }


def test_sanitize_when_step_keeps_var_op_passed():
    entry = {"type": "when", "var": "snap.verdict", "op": "equals",
             "passed": False, "status": "ok"}
    out = triggers._sanitize_step_entry(entry)
    assert out["type"] == "when"
    assert out["var"] == "snap.verdict"
    assert out["op"] == "equals"
    assert out["passed"] is False


# ---------------------------------------------------------------------------
# _sanitize_run_for_revise: full context projection
# ---------------------------------------------------------------------------


def test_sanitize_run_strips_canary_from_run_log():
    run_log = [
        {"type": "call", "call": "imessage_current", "status": "ok",
         "result": f'{{"last_text": "{CANARY}"}}'},
        {"type": "call", "call": "block_domain", "status": "error",
         "error_category": "step_returned_error",
         "error": f"reason involving {CANARY}"},
    ]
    locals_dict = {"chat": {"handle": "+15551234567", "last_text": CANARY}}
    out = triggers._sanitize_run_for_revise(run_log, locals_dict, fatal_error=None)
    serialized = json.dumps(out)
    assert CANARY not in serialized


def test_sanitize_run_strips_canary_from_locals():
    run_log = []
    locals_dict = {"snap": {"verdict": "distracted", "details": CANARY}}
    out = triggers._sanitize_run_for_revise(run_log, locals_dict, fatal_error=None)
    assert CANARY not in json.dumps(out)
    # but the keys are preserved so the agent can debug paths
    assert "snap" in out["locals_skeleton"]
    assert "verdict" in out["locals_skeleton"]["snap"]
    assert "details" in out["locals_skeleton"]["snap"]


def test_sanitize_run_strips_canary_from_fatal_error_keeps_type():
    out = triggers._sanitize_run_for_revise(
        [], {}, fatal_error=f"RuntimeError: leaked {CANARY}")
    assert out["fatal_error_type"] == "RuntimeError"
    assert CANARY not in json.dumps(out)


def test_sanitize_run_drops_non_exception_fatal_error():
    out = triggers._sanitize_run_for_revise(
        [], {}, fatal_error=f"3 step(s) failed: block_domain({CANARY})")
    assert out["fatal_error_type"] is None
    assert CANARY not in json.dumps(out)


def test_sanitize_run_counts_failed_steps():
    run_log = [
        {"type": "call", "call": "a", "status": "ok"},
        {"type": "call", "call": "b", "status": "error", "error_category": "x"},
        {"type": "call", "call": "c", "status": "error", "error_category": "y"},
    ]
    out = triggers._sanitize_run_for_revise(run_log, {}, None)
    assert out["failed_step_count"] == 2


# ---------------------------------------------------------------------------
# Full prompt formatting: end-to-end injection canary
# ---------------------------------------------------------------------------


def test_revise_prompt_format_does_not_leak_canary():
    """The fully-formatted REVISE_PROMPT must not contain the canary."""
    failure = {
        "steps": [
            {"type": "call", "call": "imessage_current", "status": "ok",
             "result": f'{{"last_text": "{CANARY}"}}'},
            {"type": "call", "call": "notify", "status": "error",
             "error_category": "step_returned_error",
             "error": f"reason: {CANARY}"},
        ],
        "locals": {
            "chat": {"handle": "+15551234567", "last_text": CANARY},
            "alert_text": CANARY,
        },
        "error": f"1 step(s) failed: notify({CANARY})",
    }
    sanitized = triggers._sanitize_run_for_revise(
        failure["steps"], failure["locals"], failure["error"])
    calls_desc = "\n".join(f"- {k}: {v}" for k, v in triggers.list_calls().items())
    prompt = triggers.REVISE_PROMPT.format(
        request="user's original request was clean",
        prior_spec=json.dumps({"name": "x", "recipe": {"steps": []}}),
        sanitized=json.dumps(sanitized, indent=2),
        calls=calls_desc,
    )
    # The single non-negotiable assertion: NO canary anywhere in the prompt.
    assert CANARY not in prompt


def test_revise_prompt_via_revise_function_does_not_leak_canary():
    """End-to-end through _revise_from_failure with a mocked LLM."""
    captured_prompts = []

    async def fake_call_gemini(api_key, prompt, max_tokens=4000):
        captured_prompts.append(prompt)
        return json.dumps({
            "name": "fixed", "interval_sec": 60,
            "recipe": {"steps": [{"call": "now", "save_as": "t"}]},
        })

    failure = {
        "steps": [
            {"type": "call", "call": "block_domain", "status": "error",
             "error_category": "step_returned_error",
             "error": f"reason involving payload {CANARY}",
             "result": f'{{"reason": "{CANARY}"}}'},
        ],
        "locals": {"target": CANARY},
        "error": f"step_raised: PayloadError: {CANARY}",
    }
    with patch("sentinel.classifier.call_gemini", side_effect=fake_call_gemini):
        asyncio.run(triggers._revise_from_failure(
            "fake-api-key", "user wanted to block twitter", {"name": "v1"}, failure))
    assert len(captured_prompts) == 1
    assert CANARY not in captured_prompts[0]


def test_revise_prompt_carries_useful_info():
    """Sanitization is not over-eager — the agent still gets enough to debug."""
    failure = {
        "steps": [
            {"type": "call", "call": "block_domain", "status": "error",
             "error_category": "step_returned_error",
             "error": "ignored"},
            {"type": "call", "call": "log", "status": "ok",
             "result": "ignored"},
        ],
        "locals": {
            "cur": {"app": "Cursor", "title": "x", "domain": "", "url": ""},
        },
        "error": None,
    }
    sanitized = triggers._sanitize_run_for_revise(
        failure["steps"], failure["locals"], failure["error"])
    s = json.dumps(sanitized)
    # The LLM can see what went wrong
    assert "step_returned_error" in s
    assert "block_domain" in s
    # The LLM can see the available keys to fix var paths
    assert "cur" in s
    assert "domain" in s
    # But not the values
    assert "Cursor" not in s


# ---------------------------------------------------------------------------
# End-to-end through run_once: a real failed trigger gets sanitized
# ---------------------------------------------------------------------------


def test_run_once_failure_then_revise_sanitizes(conn):
    """A real failed step's payload-shaped error doesn't leak into revise."""
    # Build a step that returns a result containing the canary, then fails
    triggers.create(conn, "leaky", {"steps": [
        {"call": "kv_set", "args": {"namespace": "test", "key": "x",
                                    "value": CANARY}},
        {"call": "kv_get", "args": {"namespace": "test", "key": "x"},
         "save_as": "leaked"},
        {"call": "block_domain", "args": {"domain": ""}},  # this one fails
    ]}, interval_sec=60)
    out = triggers.run_once(conn, "leaky")
    assert out["status"] == "error"
    # The locals dict has the canary in it (we set it via kv_set)
    assert CANARY in json.dumps(out["locals"], default=str)
    # But the sanitized version for revise must not
    sanitized = triggers._sanitize_run_for_revise(
        out["steps"], out["locals"], out["error"])
    assert CANARY not in json.dumps(sanitized)


def test_unknown_call_carries_error_category(conn):
    """The new error_category field is set on every error path."""
    # Bypass validate_recipe by writing directly. Make sure the table exists
    # by going through a normal create first.
    triggers.create(conn, "_init", {"steps": []}, interval_sec=60)
    triggers.delete(conn, "_init", force=True)
    import json as _j
    conn.execute(
        "INSERT INTO agent_triggers (name, interval_sec, recipe, created_at) "
        "VALUES (?, ?, ?, ?)",
        ("bypass", 60, _j.dumps({"steps": [{"call": "definitely_fake_op"}]}), 1.0))
    conn.commit()
    out = triggers.run_once(conn, "bypass")
    assert out["status"] == "error"
    err_step = next(s for s in out["steps"] if s.get("call") == "definitely_fake_op")
    assert err_step["error_category"] == "unknown_call"


def test_step_raised_carries_exception_type(conn):
    """When a call raises, exception_type is recorded but not the message."""
    triggers.create(conn, "raises", {"steps": [
        {"call": "kv_set", "args": {"namespace": "x", "key": "k", "value": 1}},
    ]}, interval_sec=60)
    with patch("sentinel.ai_store.kv_set",
               side_effect=ValueError(f"my error contains {CANARY}")):
        out = triggers.run_once(conn, "raises")
    err_step = next(s for s in out["steps"] if s.get("call") == "kv_set")
    assert err_step["error_category"] == "step_raised"
    assert err_step["exception_type"] == "ValueError"
    # The raw entry KEEPS the message for the run-history debugger
    assert CANARY in err_step.get("error", "")
    # But sanitization drops it
    sanitized_step = triggers._sanitize_step_entry(err_step)
    assert "error" not in sanitized_step
    assert CANARY not in json.dumps(sanitized_step)
