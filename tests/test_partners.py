"""Tests for sentinel.partners — accountability partner notifications."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from sentinel import partners


class TestAddPartner:
    def test_add_returns_id(self, conn):
        pid = partners.add_partner(conn, "Alice", "https://hook.example/a")
        assert pid >= 1

    def test_add_default_method_webhook(self, conn):
        pid = partners.add_partner(conn, "Bob", "https://hook.example/b")
        p = partners.get_partner(conn, pid)
        assert p["method"] == "webhook"

    def test_add_email_method(self, conn):
        pid = partners.add_partner(conn, "Carol", "carol@example.com", method="email")
        p = partners.get_partner(conn, pid)
        assert p["method"] == "email"

    def test_add_stores_contact(self, conn):
        pid = partners.add_partner(conn, "Dan", "+15551234567", method="sms")
        p = partners.get_partner(conn, pid)
        assert p["contact"] == "+15551234567"

    def test_add_sets_created_at(self, conn):
        pid = partners.add_partner(conn, "Eve", "x")
        p = partners.get_partner(conn, pid)
        assert p["created_at"] > 0


class TestGetPartners:
    def test_empty_list(self, conn):
        assert partners.get_partners(conn) == []

    def test_lists_in_order(self, conn):
        a = partners.add_partner(conn, "A", "u1")
        b = partners.add_partner(conn, "B", "u2")
        out = partners.get_partners(conn)
        assert [p["id"] for p in out] == [a, b]

    def test_list_includes_method(self, conn):
        partners.add_partner(conn, "A", "u1", method="sms")
        out = partners.get_partners(conn)
        assert out[0]["method"] == "sms"


class TestDeletePartner:
    def test_delete_removes(self, conn):
        pid = partners.add_partner(conn, "A", "u")
        partners.delete_partner(conn, pid)
        assert partners.get_partner(conn, pid) is None

    def test_delete_missing_ok(self, conn):
        partners.delete_partner(conn, 9999)  # should not raise

    def test_delete_leaves_others(self, conn):
        a = partners.add_partner(conn, "A", "u1")
        b = partners.add_partner(conn, "B", "u2")
        partners.delete_partner(conn, a)
        remaining = [p["id"] for p in partners.get_partners(conn)]
        assert remaining == [b]


class TestNotifyPartners:
    def test_notify_empty(self, conn):
        result = asyncio.run(partners.notify_partners(conn, "test", {}))
        assert result == []

    def test_notify_webhook_success(self, conn):
        partners.add_partner(conn, "A", "https://hook.example/a", method="webhook")

        async def fake_post(self, url, json=None):
            class R:
                status_code = 200
            return R()

        with patch("httpx.AsyncClient.post", new=fake_post):
            result = asyncio.run(partners.notify_partners(conn, "violation", {"rule": 1}))
        assert result[0]["ok"] is True
        assert result[0]["method"] == "webhook"

    def test_notify_webhook_failure(self, conn):
        partners.add_partner(conn, "A", "https://hook.example/a", method="webhook")

        async def fake_post(self, url, json=None):
            raise RuntimeError("network down")

        with patch("httpx.AsyncClient.post", new=fake_post):
            result = asyncio.run(partners.notify_partners(conn, "violation", {}))
        assert result[0]["ok"] is False

    def test_notify_email_logs_only(self, conn):
        partners.add_partner(conn, "A", "a@x.com", method="email")
        result = asyncio.run(partners.notify_partners(conn, "test", {"k": "v"}))
        assert result[0]["method"] == "email"
        assert result[0]["ok"] is True

    def test_notify_sms_logs_only(self, conn):
        partners.add_partner(conn, "A", "+15550", method="sms")
        result = asyncio.run(partners.notify_partners(conn, "test", {}))
        assert result[0]["method"] == "sms"
        assert result[0]["ok"] is True
