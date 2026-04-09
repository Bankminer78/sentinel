"""Tests for sentinel.client — Python API client."""

import asyncio
from unittest.mock import patch

import pytest

from sentinel.client import SentinelClient


class _Resp:
    def __init__(self, payload=None, status=200):
        self._p = payload if payload is not None else {}
        self.status_code = status

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _mk_get(payload):
    async def get(self, url, **kw):
        get.last_url = url
        get.last_kw = kw
        return _Resp(payload)
    return get


def _mk_post(payload):
    async def post(self, url, json=None):
        post.last_url = url
        post.last_json = json
        return _Resp(payload)
    return post


def _mk_delete(payload):
    async def delete(self, url):
        delete.last_url = url
        return _Resp(payload)
    return delete


class TestInit:
    def test_default_url(self):
        c = SentinelClient()
        assert c.base_url == "http://localhost:9849"

    def test_strips_trailing_slash(self):
        c = SentinelClient("http://foo:1234/")
        assert c.base_url == "http://foo:1234"


class TestRules:
    def test_add_rule(self):
        c = SentinelClient()
        fp = _mk_post({"id": 7, "text": "hi"})
        with patch("httpx.AsyncClient.post", new=fp):
            result = asyncio.run(c.add_rule("block X"))
        assert result["id"] == 7
        assert fp.last_json == {"text": "block X"}
        assert fp.last_url.endswith("/rules")

    def test_list_rules(self):
        c = SentinelClient()
        with patch("httpx.AsyncClient.get", new=_mk_get([{"id": 1}])):
            result = asyncio.run(c.list_rules())
        assert result == [{"id": 1}]

    def test_delete_rule(self):
        c = SentinelClient()
        fd = _mk_delete({"ok": True})
        with patch("httpx.AsyncClient.delete", new=fd):
            asyncio.run(c.delete_rule(3))
        assert fd.last_url.endswith("/rules/3")

    def test_toggle_rule(self):
        c = SentinelClient()
        fp = _mk_post({"ok": True})
        with patch("httpx.AsyncClient.post", new=fp):
            asyncio.run(c.toggle_rule(5))
        assert fp.last_url.endswith("/rules/5/toggle")


class TestStatus:
    def test_status(self):
        c = SentinelClient()
        with patch("httpx.AsyncClient.get", new=_mk_get({"active_rules": []})):
            result = asyncio.run(c.status())
        assert "active_rules" in result

    def test_stats(self):
        c = SentinelClient()
        with patch("httpx.AsyncClient.get", new=_mk_get({"blocked_count": 4})):
            result = asyncio.run(c.stats())
        assert result["blocked_count"] == 4


class TestBlocking:
    def test_block(self):
        c = SentinelClient()
        fp = _mk_post({"ok": True})
        with patch("httpx.AsyncClient.post", new=fp):
            asyncio.run(c.block("youtube.com"))
        assert fp.last_url.endswith("/block/domain/youtube.com")

    def test_unblock(self):
        c = SentinelClient()
        fd = _mk_delete({"ok": True})
        with patch("httpx.AsyncClient.delete", new=fd):
            asyncio.run(c.unblock("youtube.com"))
        assert fd.last_url.endswith("/block/domain/youtube.com")


class TestSessions:
    def test_start_focus(self):
        c = SentinelClient()
        fp = _mk_post({"id": 1})
        with patch("httpx.AsyncClient.post", new=fp):
            asyncio.run(c.start_focus(60, locked=True))
        assert fp.last_json == {"duration_minutes": 60, "locked": True}

    def test_start_pomodoro(self):
        c = SentinelClient()
        fp = _mk_post({"id": 2})
        with patch("httpx.AsyncClient.post", new=fp):
            asyncio.run(c.start_pomodoro(work=50, br=10))
        assert fp.last_json["work_minutes"] == 50
        assert fp.last_json["break_minutes"] == 10


class TestScoresAndAsk:
    def test_get_score(self):
        c = SentinelClient()
        with patch("httpx.AsyncClient.get", new=_mk_get({"score": 87.5})):
            result = asyncio.run(c.get_score())
        assert result == 87.5

    def test_ask(self):
        c = SentinelClient()
        fp = _mk_post({"answer": "yes"})
        with patch("httpx.AsyncClient.post", new=fp):
            result = asyncio.run(c.ask("is it working?"))
        assert result == "yes"
        assert fp.last_json == {"question": "is it working?"}


class TestGoals:
    def test_add_goal(self):
        c = SentinelClient()
        fp = _mk_post({"id": 99})
        with patch("httpx.AsyncClient.post", new=fp):
            result = asyncio.run(c.add_goal("focus", "max_seconds", 3600))
        assert result["id"] == 99
        assert fp.last_json == {"name": "focus", "target_type": "max_seconds", "target_value": 3600}
