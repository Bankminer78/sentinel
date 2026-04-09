"""Tests for sentinel.webhooks."""
import hmac, hashlib
import pytest
from unittest.mock import patch
from sentinel import webhooks


def test_register_webhook(conn):
    path = webhooks.register_webhook(conn, "test", "s3cret", "notify")
    assert path.startswith("/webhooks/in/")
    wid = path.rsplit("/", 1)[-1]
    assert len(wid) == 16


def test_list_webhooks_empty(conn):
    assert webhooks.list_webhooks(conn) == []


def test_list_webhooks_after_register(conn):
    webhooks.register_webhook(conn, "a", "s1", "notify")
    webhooks.register_webhook(conn, "b", "s2", "log")
    lst = webhooks.list_webhooks(conn)
    assert len(lst) == 2
    assert {w["name"] for w in lst} == {"a", "b"}


def test_get_webhook_missing(conn):
    assert webhooks.get_webhook(conn, "nope") is None


def test_get_webhook_found(conn):
    path = webhooks.register_webhook(conn, "w", "s", "notify")
    wid = path.rsplit("/", 1)[-1]
    w = webhooks.get_webhook(conn, wid)
    assert w["name"] == "w"
    assert w["action"] == "notify"


def test_delete_webhook(conn):
    path = webhooks.register_webhook(conn, "w", "s", "notify")
    wid = path.rsplit("/", 1)[-1]
    webhooks.delete_webhook(conn, wid)
    assert webhooks.get_webhook(conn, wid) is None


def test_verify_webhook_valid(conn):
    path = webhooks.register_webhook(conn, "w", "secret", "log")
    wid = path.rsplit("/", 1)[-1]
    body = b'{"x": 1}'
    sig = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert webhooks.verify_webhook(conn, wid, sig, body) is True


def test_verify_webhook_invalid_sig(conn):
    path = webhooks.register_webhook(conn, "w", "secret", "log")
    wid = path.rsplit("/", 1)[-1]
    assert webhooks.verify_webhook(conn, wid, "bad", b"x") is False


def test_verify_webhook_unknown_id(conn):
    assert webhooks.verify_webhook(conn, "nope", "sig", b"x") is False


@pytest.mark.asyncio
async def test_handle_webhook_unknown(conn):
    result = await webhooks.handle_webhook(conn, "nope", {})
    assert result["ok"] is False
    assert result["error"] == "not_found"


@pytest.mark.asyncio
async def test_handle_webhook_log(conn):
    path = webhooks.register_webhook(conn, "w", "s", "log")
    wid = path.rsplit("/", 1)[-1]
    result = await webhooks.handle_webhook(conn, wid, {"data": 42})
    assert result["ok"] is True
    assert result["logged"] == {"data": 42}


@pytest.mark.asyncio
async def test_handle_webhook_notify(conn):
    path = webhooks.register_webhook(conn, "w", "s", "notify")
    wid = path.rsplit("/", 1)[-1]
    with patch("sentinel.notifications.notify_macos", return_value=True) as mock:
        result = await webhooks.handle_webhook(conn, wid, {"message": "hi"})
        assert result["ok"] is True
        mock.assert_called_once()


@pytest.mark.asyncio
async def test_handle_webhook_unknown_action(conn):
    path = webhooks.register_webhook(conn, "w", "s", "mystery")
    wid = path.rsplit("/", 1)[-1]
    result = await webhooks.handle_webhook(conn, wid, {})
    assert result["ok"] is False
    assert result["error"] == "unknown_action"


def test_rotate_secret(conn):
    path = webhooks.register_webhook(conn, "w", "old", "log")
    wid = path.rsplit("/", 1)[-1]
    new = webhooks.rotate_secret(conn, wid)
    assert new != "old"
    assert len(new) == 48
    assert webhooks.get_webhook(conn, wid)["secret"] == new
