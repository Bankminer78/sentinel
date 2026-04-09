"""Tests for sentinel.sms."""
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sentinel import sms, db, partners


def test_configure_twilio(conn):
    sms.configure_twilio(conn, "AC123", "tok", "+15551112222")
    cfg = sms.get_twilio_config(conn)
    assert cfg["account_sid"] == "AC123"
    assert cfg["auth_token"] == "tok"
    assert cfg["from_number"] == "+15551112222"


def test_get_twilio_config_empty(conn):
    assert sms.get_twilio_config(conn) == {}


def test_configure_twilio_persists_json(conn):
    sms.configure_twilio(conn, "AC", "t", "+1")
    raw = db.get_config(conn, "twilio_config")
    assert json.loads(raw)["account_sid"] == "AC"


@pytest.mark.asyncio
async def test_send_sms_no_config(conn):
    assert await sms.send_sms(conn, "+1555", "hi") is False


@pytest.mark.asyncio
async def test_send_sms_success(conn):
    sms.configure_twilio(conn, "AC", "tok", "+1000")
    with patch("sentinel.sms.httpx.AsyncClient") as mock_client:
        post = AsyncMock(return_value=MagicMock(status_code=201))
        mock_client.return_value.__aenter__.return_value.post = post
        ok = await sms.send_sms(conn, "+1555", "hello")
        assert ok is True
        args, kwargs = post.call_args
        assert "Messages.json" in args[0]
        assert kwargs["data"]["Body"] == "hello"
        assert kwargs["data"]["To"] == "+1555"
        assert kwargs["data"]["From"] == "+1000"


@pytest.mark.asyncio
async def test_send_sms_http_error(conn):
    sms.configure_twilio(conn, "AC", "tok", "+1000")
    with patch("sentinel.sms.httpx.AsyncClient") as mock_client:
        post = AsyncMock(return_value=MagicMock(status_code=500))
        mock_client.return_value.__aenter__.return_value.post = post
        assert await sms.send_sms(conn, "+1555", "x") is False


@pytest.mark.asyncio
async def test_send_sms_exception(conn):
    sms.configure_twilio(conn, "AC", "tok", "+1000")
    with patch("sentinel.sms.httpx.AsyncClient") as mock_client:
        post = AsyncMock(side_effect=Exception("net"))
        mock_client.return_value.__aenter__.return_value.post = post
        assert await sms.send_sms(conn, "+1555", "x") is False


@pytest.mark.asyncio
async def test_send_alert_sms_no_sms_partners(conn):
    sms.configure_twilio(conn, "AC", "tok", "+1000")
    partners.add_partner(conn, "webby", "http://x", method="webhook")
    assert await sms.send_alert_sms(conn, "hi") is False


@pytest.mark.asyncio
async def test_send_alert_sms_with_partner(conn):
    sms.configure_twilio(conn, "AC", "tok", "+1000")
    partners.add_partner(conn, "sarah", "+15551234567", method="sms")
    with patch("sentinel.sms.send_sms", new_callable=AsyncMock, return_value=True) as mock:
        ok = await sms.send_alert_sms(conn, "alert")
        assert ok is True
        mock.assert_called_once()
        assert mock.call_args[0][1] == "+15551234567"


@pytest.mark.asyncio
async def test_send_alert_sms_partial_failure(conn):
    sms.configure_twilio(conn, "AC", "tok", "+1000")
    partners.add_partner(conn, "a", "+11", method="sms")
    partners.add_partner(conn, "b", "+22", method="sms")
    with patch("sentinel.sms.send_sms", new_callable=AsyncMock, side_effect=[False, True]):
        assert await sms.send_alert_sms(conn, "alert") is True


def test_test_twilio_config_no_config(conn):
    assert sms.test_twilio_config(conn) is False


def test_test_twilio_config_success(conn):
    sms.configure_twilio(conn, "AC", "tok", "+1000")
    with patch("sentinel.sms.httpx.Client") as mock_client:
        get = MagicMock(return_value=MagicMock(status_code=200))
        mock_client.return_value.__enter__.return_value.get = get
        assert sms.test_twilio_config(conn) is True


def test_test_twilio_config_failure(conn):
    sms.configure_twilio(conn, "AC", "tok", "+1000")
    with patch("sentinel.sms.httpx.Client", side_effect=Exception("x")):
        assert sms.test_twilio_config(conn) is False
