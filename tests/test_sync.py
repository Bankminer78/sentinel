"""Tests for sentinel.sync — cross-device sync via HTTP."""

import asyncio
import json
from unittest.mock import patch

import pytest

from sentinel import db, partners, stats, sync


class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


def _fake_post(payload=None, status=200):
    async def post(self, url, json=None):
        post.last_url = url
        post.last_payload = json
        return _Resp(status, payload)
    return post


def _fake_get(payload=None, status=200):
    async def get(self, url, params=None):
        get.last_url = url
        get.last_params = params
        return _Resp(status, payload)
    return get


class TestDeviceId:
    def test_set_and_get(self, conn):
        sync.set_device_id(conn, "abc123")
        assert sync.get_device_id(conn) == "abc123"

    def test_get_autogenerates(self, conn):
        did = sync.get_device_id(conn)
        assert did and len(did) >= 8
        # Persists
        assert sync.get_device_id(conn) == did


class TestSyncUrl:
    def test_set_and_get(self, conn):
        sync.set_sync_url(conn, "https://sync.example.com")
        assert sync.get_sync_url(conn) == "https://sync.example.com"

    def test_get_default_empty(self, conn):
        assert sync.get_sync_url(conn) == ""


class TestPush:
    def test_push_success(self, conn):
        db.add_rule(conn, "Block YouTube")
        fp = _fake_post()
        with patch("httpx.AsyncClient.post", new=fp):
            result = asyncio.run(sync.push_to_sync(conn, "https://s.io", "dev1"))
        assert result["ok"] is True
        assert result["pushed"] == 1
        assert fp.last_url.endswith("/sync/push")
        assert fp.last_payload["device_id"] == "dev1"
        assert "rules" in fp.last_payload["data"]

    def test_push_includes_seen_domains(self, conn):
        db.save_seen(conn, "example.com", "productive")
        fp = _fake_post()
        with patch("httpx.AsyncClient.post", new=fp):
            asyncio.run(sync.push_to_sync(conn, "https://s.io", "dev1"))
        seen = fp.last_payload["data"]["seen_domains"]
        assert any(s["domain"] == "example.com" for s in seen)

    def test_push_handles_trailing_slash(self, conn):
        fp = _fake_post()
        with patch("httpx.AsyncClient.post", new=fp):
            asyncio.run(sync.push_to_sync(conn, "https://s.io/", "dev1"))
        assert "//sync/push" not in fp.last_url

    def test_push_server_error(self, conn):
        with patch("httpx.AsyncClient.post", new=_fake_post(status=500)):
            result = asyncio.run(sync.push_to_sync(conn, "https://s.io", "dev1"))
        assert result["ok"] is False
        assert "500" in result["error"]

    def test_push_network_error(self, conn):
        async def bad_post(self, url, json=None):
            raise RuntimeError("network down")
        with patch("httpx.AsyncClient.post", new=bad_post):
            result = asyncio.run(sync.push_to_sync(conn, "https://s.io", "dev1"))
        assert result["ok"] is False
        assert "network down" in result["error"]


class TestPull:
    def test_pull_merges_rules(self, conn):
        remote = {"data": {"rules": [{"text": "Remote rule"}],
                           "goals": [], "partners": [], "config": {},
                           "seen_domains": []}}
        with patch("httpx.AsyncClient.get", new=_fake_get(remote)):
            result = asyncio.run(sync.pull_from_sync(conn, "https://s.io", "dev1"))
        assert result["ok"] is True
        assert result["rules"] == 1
        assert db.get_rules(conn)[0]["text"] == "Remote rule"

    def test_pull_merges_seen_domains(self, conn):
        remote = {"data": {"rules": [], "goals": [], "partners": [], "config": {},
                           "seen_domains": [{"domain": "foo.com", "category": "social", "first_seen": 1.0}]}}
        with patch("httpx.AsyncClient.get", new=_fake_get(remote)):
            result = asyncio.run(sync.pull_from_sync(conn, "https://s.io", "dev1"))
        assert result["seen_domains"] == 1
        assert db.get_seen(conn, "foo.com") == "social"

    def test_pull_skips_existing_seen(self, conn):
        db.save_seen(conn, "foo.com", "productive")
        remote = {"data": {"rules": [], "goals": [], "partners": [], "config": {},
                           "seen_domains": [{"domain": "foo.com", "category": "social"}]}}
        with patch("httpx.AsyncClient.get", new=_fake_get(remote)):
            result = asyncio.run(sync.pull_from_sync(conn, "https://s.io", "dev1"))
        assert result["seen_domains"] == 0
        assert db.get_seen(conn, "foo.com") == "productive"

    def test_pull_server_error(self, conn):
        with patch("httpx.AsyncClient.get", new=_fake_get(status=503)):
            result = asyncio.run(sync.pull_from_sync(conn, "https://s.io", "dev1"))
        assert result["ok"] is False

    def test_pull_network_error(self, conn):
        async def bad_get(self, url, params=None):
            raise RuntimeError("boom")
        with patch("httpx.AsyncClient.get", new=bad_get):
            result = asyncio.run(sync.pull_from_sync(conn, "https://s.io", "dev1"))
        assert result["ok"] is False
        assert "boom" in result["error"]

    def test_pull_passes_device_id(self, conn):
        fg = _fake_get({"data": {"rules": []}})
        with patch("httpx.AsyncClient.get", new=fg):
            asyncio.run(sync.pull_from_sync(conn, "https://s.io", "devZ"))
        assert fg.last_params == {"device_id": "devZ"}
