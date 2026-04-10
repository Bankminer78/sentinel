"""Tests for sentinel.agent — the Claude session host.

The actual `claude_agent_sdk.query()` call is mocked because we don't want
to hit the real Claude API in unit tests. The end-to-end smoke test that
DOES hit Claude is gated behind SENTINEL_LIVE_TESTS=1 and lives in
test_agent_live.py.
"""
import asyncio
import json
import os
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from sentinel import agent, ai_store, audit, db


# ---------------------------------------------------------------------------
# Token budget tracking
# ---------------------------------------------------------------------------


def test_default_budget_when_unset(conn):
    assert agent.get_budget_usd(conn) == agent.DEFAULT_BUDGET_USD


def test_budget_from_config(conn):
    db.set_config(conn, "daily_token_budget_usd", "0.50")
    assert agent.get_budget_usd(conn) == 0.50


def test_invalid_budget_falls_back_to_default(conn):
    db.set_config(conn, "daily_token_budget_usd", "garbage")
    assert agent.get_budget_usd(conn) == agent.DEFAULT_BUDGET_USD


def test_used_today_zero_by_default(conn):
    assert agent.get_used_today_usd(conn) == 0.0


def test_add_usage_increments(conn):
    agent.add_usage_usd(conn, 0.10)
    assert agent.get_used_today_usd(conn) == pytest.approx(0.10)
    agent.add_usage_usd(conn, 0.05)
    assert agent.get_used_today_usd(conn) == pytest.approx(0.15)


def test_remaining_budget(conn):
    db.set_config(conn, "daily_token_budget_usd", "1.00")
    agent.add_usage_usd(conn, 0.25)
    assert agent.remaining_budget_usd(conn) == pytest.approx(0.75)


def test_remaining_budget_clamps_at_zero(conn):
    db.set_config(conn, "daily_token_budget_usd", "0.10")
    agent.add_usage_usd(conn, 0.50)
    assert agent.remaining_budget_usd(conn) == 0.0


def test_used_today_resets_per_calendar_day(conn):
    """Yesterday's usage doesn't count against today."""
    yesterday = "2020-01-01"
    ai_store.kv_set(conn, agent.TOKEN_METER_NAMESPACE, yesterday, 0.99)
    # Today is whatever _today_key returns; should be empty
    assert agent.get_used_today_usd(conn) == 0.0


# ---------------------------------------------------------------------------
# Audit hook
# ---------------------------------------------------------------------------


def test_audit_hook_logs_bash_invocation(conn):
    hook = agent._make_audit_hook(conn, "test_session")
    asyncio.run(hook(
        {"tool_name": "Bash",
         "tool_input": {"command": "python3 -c 'print(1)'",
                        "description": "test command"}},
        "tool_use_123",
        None,
    ))
    rows = audit.list_recent(conn, primitive="agent_tool.Bash")
    assert len(rows) == 1
    assert rows[0]["actor"] == "agent:test_session"
    assert rows[0]["args_summary"]["command"] == "python3 -c 'print(1)'"
    assert rows[0]["args_summary"]["description"] == "test command"
    assert rows[0]["result_status"] == "invoked"


def test_audit_hook_truncates_long_command(conn):
    hook = agent._make_audit_hook(conn, "session_x")
    long_command = "x" * 5000
    asyncio.run(hook(
        {"tool_name": "Bash", "tool_input": {"command": long_command}},
        None, None,
    ))
    rows = audit.list_recent(conn, primitive="agent_tool.Bash")
    assert len(rows[0]["args_summary"]["command"]) == 1000


def test_audit_hook_handles_unknown_tool(conn):
    """A non-Bash tool should still get logged with truncated args."""
    hook = agent._make_audit_hook(conn, "s")
    asyncio.run(hook(
        {"tool_name": "Read", "tool_input": {"path": "/tmp/foo", "extra": "x" * 500}},
        None, None,
    ))
    rows = audit.list_recent(conn, primitive="agent_tool.Read")
    assert len(rows) == 1
    assert rows[0]["args_summary"]["path"] == "/tmp/foo"
    assert len(rows[0]["args_summary"]["extra"]) == 200


def test_audit_hook_never_throws(conn):
    """Even a malformed input should not raise — agent flow must continue."""
    hook = agent._make_audit_hook(conn, "s")
    # Garbage input
    result = asyncio.run(hook(None, None, None))
    assert result == {}


# ---------------------------------------------------------------------------
# run_session: budget refusal path (no SDK call)
# ---------------------------------------------------------------------------


def test_run_session_refused_when_budget_exhausted(conn):
    db.set_config(conn, "daily_token_budget_usd", "0.10")
    agent.add_usage_usd(conn, 0.20)  # over budget

    async def collect():
        events = []
        async for event in agent.run_session("anything", conn=conn):
            events.append(event)
        return events

    events = asyncio.run(collect())
    assert len(events) == 1
    assert events[0]["type"] == "budget_refused"
    assert events[0]["budget_usd"] == 0.10
    assert events[0]["used_usd"] == pytest.approx(0.20)
    # Audit log captures the refusal
    rows = audit.list_recent(conn, primitive="agent.session_refused")
    assert len(rows) == 1
    assert rows[0]["result_status"] == "budget_refused"


def test_run_session_proceeds_when_under_budget(conn):
    db.set_config(conn, "daily_token_budget_usd", "1.00")
    agent.add_usage_usd(conn, 0.10)  # plenty left

    # Mock the SDK's query() to yield a single fake result message
    async def fake_query(*, prompt, options, transport=None):
        from claude_agent_sdk import ResultMessage
        # Build a minimal ResultMessage-like fake
        msg = MagicMock(spec=ResultMessage)
        msg.result = "fake answer"
        msg.total_cost_usd = 0.005
        msg.subtype = "success"
        yield msg

    with patch("sentinel.agent.query", side_effect=fake_query):
        async def collect():
            events = []
            async for event in agent.run_session("test prompt", conn=conn):
                events.append(event)
            return events
        events = asyncio.run(collect())

    types = [e["type"] for e in events]
    assert "session_started" in types
    assert "result" in types
    # The cost was added to today's usage
    assert agent.get_used_today_usd(conn) == pytest.approx(0.105)
    # Audit log shows the lifecycle
    started = audit.list_recent(conn, primitive="agent.session_started")
    finished = audit.list_recent(conn, primitive="agent.session_finished")
    assert len(started) == 1
    assert len(finished) == 1


def test_run_session_streams_text_deltas(conn):
    """StreamEvent content_block_delta → assistant_text_delta events.

    In streaming mode (include_partial_messages=True), text arrives via
    StreamEvent, not via AssistantMessage.TextBlock. The AssistantMessage
    is intentionally skipped for TextBlocks to avoid the duplicate-text
    bug that was reported in production.
    """
    db.set_config(conn, "daily_token_budget_usd", "1.00")

    async def fake_query(*, prompt, options, transport=None):
        from claude_agent_sdk import StreamEvent, AssistantMessage, TextBlock, ResultMessage
        # 1. StreamEvent: content_block_start for a text block
        yield MagicMock(spec=StreamEvent, event={
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "text", "text": ""},
        })
        # 2. StreamEvent: two text deltas
        yield MagicMock(spec=StreamEvent, event={
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "I'll do "},
        })
        yield MagicMock(spec=StreamEvent, event={
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "that now."},
        })
        # 3. AssistantMessage with the full text (should be SUPPRESSED)
        m = MagicMock(spec=AssistantMessage)
        block = MagicMock(spec=TextBlock)
        block.text = "I'll do that now."
        m.content = [block]
        yield m
        # 4. ResultMessage
        r = MagicMock(spec=ResultMessage)
        r.result = "I'll do that now."
        r.total_cost_usd = 0
        r.subtype = "success"
        yield r

    with patch("sentinel.agent.query", side_effect=fake_query):
        async def collect():
            return [e async for e in agent.run_session("hi", conn=conn)]
        events = asyncio.run(collect())

    # The text arrived via deltas, NOT via assistant_text
    delta_events = [e for e in events if e["type"] == "assistant_text_delta"]
    assert len(delta_events) == 2
    assert delta_events[0]["delta"] == "I'll do "
    assert delta_events[1]["delta"] == "that now."

    # No assistant_text fallback (the duplicate bug was exactly this)
    fallback = [e for e in events if e["type"] == "assistant_text"]
    assert len(fallback) == 0


def test_run_session_streams_tool_use_blocks(conn):
    db.set_config(conn, "daily_token_budget_usd", "1.00")

    async def fake_query(*, prompt, options, transport=None):
        from claude_agent_sdk import AssistantMessage, ToolUseBlock, ResultMessage
        m = MagicMock(spec=AssistantMessage)
        block = MagicMock(spec=ToolUseBlock)
        block.name = "Bash"
        block.input = {"command": "python3 -c 'print(1)'"}
        m.content = [block]
        yield m
        r = MagicMock(spec=ResultMessage)
        r.result = "done"
        r.total_cost_usd = 0
        r.subtype = "success"
        yield r

    with patch("sentinel.agent.query", side_effect=fake_query):
        async def collect():
            return [e async for e in agent.run_session("hi", conn=conn)]
        events = asyncio.run(collect())

    tool_events = [e for e in events if e["type"] == "tool_use"]
    assert len(tool_events) == 1
    assert tool_events[0]["tool"] == "Bash"


def test_run_session_handles_query_exception(conn):
    db.set_config(conn, "daily_token_budget_usd", "1.00")

    async def fake_query(*, prompt, options, transport=None):
        if False:
            yield  # make this a generator
        raise RuntimeError("simulated SDK failure")

    with patch("sentinel.agent.query", side_effect=fake_query):
        async def collect():
            return [e async for e in agent.run_session("hi", conn=conn)]
        events = asyncio.run(collect())

    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["error_type"] == "RuntimeError"
    # Audit log captures the error
    err_rows = audit.list_recent(conn, primitive="agent.session_errored")
    assert len(err_rows) == 1


def test_run_session_truncate_helper():
    """The internal _truncate keeps small values intact and trims big ones."""
    # Small value: comes back as-is (after JSON round-trip)
    assert agent._truncate({"a": 1}) == {"a": 1}
    # Big value: trimmed
    big = {"text": "x" * 5000}
    out = agent._truncate(big, max_len=200)
    assert isinstance(out, str)
    assert "…" in out
    assert len(out) <= 250  # ~200 + ellipsis + JSON quoting overhead


def test_session_id_is_generated_when_omitted(conn):
    db.set_config(conn, "daily_token_budget_usd", "1.00")

    async def fake_query(*, prompt, options, transport=None):
        from claude_agent_sdk import ResultMessage
        r = MagicMock(spec=ResultMessage)
        r.result = "done"
        r.total_cost_usd = 0
        r.subtype = "success"
        yield r

    with patch("sentinel.agent.query", side_effect=fake_query):
        async def collect():
            return [e async for e in agent.run_session("hi", conn=conn)]
        events = asyncio.run(collect())

    sids = {e.get("session_id") for e in events if e.get("session_id")}
    assert len(sids) == 1  # all events share the same session_id
    assert len(next(iter(sids))) == 12  # uuid.hex[:12]


def test_session_id_is_respected_when_passed(conn):
    db.set_config(conn, "daily_token_budget_usd", "1.00")

    async def fake_query(*, prompt, options, transport=None):
        from claude_agent_sdk import ResultMessage
        r = MagicMock(spec=ResultMessage)
        r.result = "done"
        r.total_cost_usd = 0
        r.subtype = "success"
        yield r

    with patch("sentinel.agent.query", side_effect=fake_query):
        async def collect():
            return [e async for e in agent.run_session("hi", session_id="my_sid", conn=conn)]
        events = asyncio.run(collect())

    assert all(e.get("session_id") == "my_sid" for e in events if e.get("session_id"))
