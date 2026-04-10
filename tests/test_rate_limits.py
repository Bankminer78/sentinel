"""Tests for per-recipe and per-primitive rate limits.

Catches runaway recipes that the static validator can't detect (e.g. a
nested when-loop that fires hundreds of http_fetch calls). The limits
are intentionally loose enough that real recipes don't trip them, but
strict enough that a malicious or buggy recipe gets cut off quickly.
"""
import pytest
from unittest.mock import patch
from sentinel import triggers


def test_per_run_total_cap_default(conn):
    """The DEFAULT_MAX_CALLS_PER_RUN cap fires when a recipe makes too many calls."""
    # Build a recipe that calls `now` 60 times — past the default 50 cap
    steps = [{"call": "now", "save_as": f"t{i}"} for i in range(60)]
    triggers.create(conn, "many_calls", {"steps": steps}, interval_sec=60)
    out = triggers.run_once(conn, "many_calls")
    assert out["status"] == "error"
    # First 50 should have run successfully
    ok_steps = [s for s in out["steps"] if s.get("status") == "ok"]
    assert len(ok_steps) == 50
    # The remaining 10 should have rate_limit set
    rate_limited = [s for s in out["steps"] if s.get("rate_limit") == "total_per_run"]
    assert len(rate_limited) == 10


def test_per_run_cap_respects_recipe_override(conn):
    """A recipe can lower its own cap via max_calls_per_run."""
    steps = [{"call": "now", "save_as": f"t{i}"} for i in range(20)]
    triggers.create(conn, "tight_cap", {
        "max_calls_per_run": 5,
        "steps": steps,
    }, interval_sec=60)
    out = triggers.run_once(conn, "tight_cap")
    assert out["status"] == "error"
    ok = [s for s in out["steps"] if s.get("status") == "ok"]
    assert len(ok) == 5


def test_per_primitive_cap_http_fetch(conn):
    """http_fetch has a per-run cap of 10 (PER_PRIMITIVE_LIMITS['http_fetch'])."""
    # Don't actually make HTTP calls — patch primitives.http_fetch
    from sentinel import primitives
    with patch.object(primitives, "http_fetch",
                      return_value={"ok": True, "status": 200,
                                    "headers": {}, "body_text": "", "json": None}):
        from sentinel import sandbox
        sandbox.set_http_allowlist(conn, ["api.example.com"])
        steps = [
            {"call": "http_fetch",
             "args": {"method": "GET", "url": "https://api.example.com/x"},
             "save_as": f"r{i}"}
            for i in range(15)
        ]
        triggers.create(conn, "fetch_storm", {"steps": steps}, interval_sec=60)
        out = triggers.run_once(conn, "fetch_storm")
    assert out["status"] == "error"
    # First 10 succeeded, next 5 hit the per-primitive cap
    rate_limited = [s for s in out["steps"]
                    if s.get("rate_limit") == "per_primitive"]
    assert len(rate_limited) == 5


def test_per_primitive_cap_independent_per_call_type(conn):
    """Different primitives have independent per-run counters."""
    # 5 http_fetch + 25 sql_query + 5 screen_capture = 35 calls
    # All under their per-primitive caps (10/20/5) so should all run
    from sentinel import primitives
    with patch.object(primitives, "http_fetch",
                      return_value={"ok": True, "status": 200,
                                    "headers": {}, "body_text": "", "json": None}), \
         patch.object(primitives, "sql_query",
                      return_value={"ok": True, "rows": [], "row_count": 0}), \
         patch.object(primitives, "screen_capture",
                      return_value={"ok": True,
                                    "blob": {"_blob": "x", "size": 1, "mime": "image/png",
                                             "_bytes": b"x"}}):
        from sentinel import sandbox
        sandbox.set_http_allowlist(conn, ["api.example.com"])
        sandbox.set_sql_allowlist(conn, ["/tmp/x.db"])
        steps = (
            [{"call": "http_fetch",
              "args": {"method": "GET", "url": "https://api.example.com/x"},
              "save_as": f"h{i}"} for i in range(5)] +
            [{"call": "sql_query",
              "args": {"db_path": "/tmp/x.db", "sql": "SELECT 1"},
              "save_as": f"s{i}"} for i in range(20)] +
            [{"call": "screen_capture", "save_as": f"c{i}"} for i in range(5)]
        )
        triggers.create(conn, "mixed", {
            "max_calls_per_run": 100,  # don't trip the total cap
            "steps": steps,
        }, interval_sec=60)
        out = triggers.run_once(conn, "mixed")
    assert out["status"] == "ok"
    assert all(s.get("status") == "ok" for s in out["steps"])


def test_rate_limited_step_is_marked_as_failed(conn):
    """Rate-limited calls show up as failed steps in the run result."""
    triggers.create(conn, "x", {
        "max_calls_per_run": 2,
        "steps": [
            {"call": "now", "save_as": "a"},
            {"call": "now", "save_as": "b"},
            {"call": "now", "save_as": "c"},  # rate limited
        ],
    }, interval_sec=60)
    out = triggers.run_once(conn, "x")
    assert out["status"] == "error"
    assert "now" in out["failed_steps"]


def test_rate_limited_does_not_bind_save_as(conn):
    """A rate-limited call should not write its (nonexistent) result to locals."""
    triggers.create(conn, "x", {
        "max_calls_per_run": 1,
        "steps": [
            {"call": "now", "save_as": "first"},
            {"call": "now", "save_as": "second"},  # rate limited
        ],
    }, interval_sec=60)
    out = triggers.run_once(conn, "x")
    assert "first" in out["locals"]
    assert "second" not in out["locals"]


def test_normal_recipe_within_default_cap(conn):
    """A normal-sized recipe should never trip the default cap."""
    triggers.create(conn, "normal", {"steps": [
        {"call": "now", "save_as": "t"},
        {"call": "kv_set", "args": {"namespace": "x", "key": "k", "value": 1}},
        {"call": "kv_get", "args": {"namespace": "x", "key": "k"}, "save_as": "v"},
        {"call": "log", "args": {"message": "ok"}},
    ]}, interval_sec=60)
    out = triggers.run_once(conn, "normal")
    assert out["status"] == "ok"
    rate_limited = [s for s in out["steps"] if s.get("rate_limit")]
    assert rate_limited == []
