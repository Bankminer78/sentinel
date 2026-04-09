"""Tests for sentinel.realtime — SSE event streaming."""

import asyncio
import json

import pytest

from sentinel import realtime


@pytest.fixture(autouse=True)
def _reset_listeners():
    realtime.clear_listeners()
    yield
    realtime.clear_listeners()


class TestSubscribe:
    def test_subscribe_returns_queue(self):
        q = realtime.subscribe()
        assert isinstance(q, asyncio.Queue)

    def test_subscribe_increments_count(self):
        assert realtime.listener_count() == 0
        realtime.subscribe()
        assert realtime.listener_count() == 1

    def test_multiple_subscribers(self):
        realtime.subscribe()
        realtime.subscribe()
        realtime.subscribe()
        assert realtime.listener_count() == 3


class TestUnsubscribe:
    def test_unsubscribe_removes(self):
        q = realtime.subscribe()
        realtime.unsubscribe(q)
        assert realtime.listener_count() == 0

    def test_unsubscribe_unknown_queue_noop(self):
        q = asyncio.Queue()
        realtime.unsubscribe(q)
        assert realtime.listener_count() == 0

    def test_unsubscribe_only_removes_target(self):
        q1 = realtime.subscribe()
        q2 = realtime.subscribe()
        realtime.unsubscribe(q1)
        assert realtime.listener_count() == 1


class TestEmitEvent:
    @pytest.mark.asyncio
    async def test_no_listeners_noop(self):
        await realtime.emit_event("test", {"x": 1})

    @pytest.mark.asyncio
    async def test_single_listener_receives(self):
        q = realtime.subscribe()
        await realtime.emit_event("activity", {"domain": "x.com"})
        payload = q.get_nowait()
        assert payload["type"] == "activity"
        assert payload["data"]["domain"] == "x.com"
        assert "ts" in payload

    @pytest.mark.asyncio
    async def test_multiple_listeners_all_receive(self):
        q1 = realtime.subscribe()
        q2 = realtime.subscribe()
        await realtime.emit_event("rule_added", {"id": 5})
        assert q1.get_nowait()["data"]["id"] == 5
        assert q2.get_nowait()["data"]["id"] == 5

    @pytest.mark.asyncio
    async def test_full_queue_does_not_raise(self):
        q = asyncio.Queue(maxsize=1)
        realtime._listeners.append(q)
        await realtime.emit_event("a", {})
        await realtime.emit_event("b", {})  # dropped, no raise
        assert q.qsize() == 1


class TestFormatSSE:
    def test_basic_frame(self):
        s = realtime.format_sse({"type": "hello", "data": {"k": 1}, "ts": 0})
        assert s.startswith("event: hello\n")
        assert "data:" in s
        assert s.endswith("\n\n")

    def test_missing_type_defaults_to_message(self):
        s = realtime.format_sse({"data": {}})
        assert "event: message" in s

    def test_data_is_json(self):
        s = realtime.format_sse({"type": "x", "data": {"foo": "bar"}})
        data_line = [ln for ln in s.splitlines() if ln.startswith("data:")][0]
        obj = json.loads(data_line[len("data: "):])
        assert obj["data"]["foo"] == "bar"


class TestEventStream:
    @pytest.mark.asyncio
    async def test_stream_yields_on_event(self):
        q = realtime.subscribe()
        gen = realtime.event_stream(q)
        await realtime.emit_event("hello", {"x": 1})
        chunk = await asyncio.wait_for(gen.__anext__(), timeout=1)
        assert "event: hello" in chunk

    @pytest.mark.asyncio
    async def test_stream_cleanup_unsubscribes(self):
        q = realtime.subscribe()
        gen = realtime.event_stream(q)
        await realtime.emit_event("x", {})
        await asyncio.wait_for(gen.__anext__(), timeout=1)
        await gen.aclose()
        assert q not in realtime._listeners
