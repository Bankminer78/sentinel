"""Tests for sentinel.push."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sentinel import push, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


@pytest.mark.asyncio
async def test_send_ntfy_success():
    mock_resp = MagicMock(status_code=200)
    with patch("sentinel.push.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        assert await push.send_ntfy("test_topic", "Title", "Message") is True


@pytest.mark.asyncio
async def test_send_ntfy_error():
    with patch("sentinel.push.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("fail"))
        assert await push.send_ntfy("topic", "T", "M") is False


@pytest.mark.asyncio
async def test_send_pushover_success():
    mock_resp = MagicMock(status_code=200)
    with patch("sentinel.push.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        assert await push.send_pushover("api_k", "user_k", "T", "M") is True


@pytest.mark.asyncio
async def test_send_telegram_success():
    mock_resp = MagicMock(status_code=200)
    with patch("sentinel.push.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        assert await push.send_telegram("bot_token", "chat_id", "hello") is True


def test_configure_ntfy(conn):
    push.configure_ntfy(conn, "my_topic")
    assert db.get_config(conn, "ntfy_topic") == "my_topic"


def test_configure_pushover(conn):
    push.configure_pushover(conn, "api", "user")
    assert db.get_config(conn, "pushover_api_key") == "api"
    assert db.get_config(conn, "pushover_user_key") == "user"


def test_configure_telegram(conn):
    push.configure_telegram(conn, "bot_token", "chat_id")
    assert db.get_config(conn, "telegram_bot_token") == "bot_token"


@pytest.mark.asyncio
async def test_send_all_push_none_configured(conn):
    result = await push.send_all_push(conn, "T", "M")
    assert result == {}


@pytest.mark.asyncio
async def test_send_all_push_ntfy_only(conn):
    push.configure_ntfy(conn, "topic")
    with patch("sentinel.push.send_ntfy", new_callable=AsyncMock, return_value=True):
        result = await push.send_all_push(conn, "T", "M")
        assert result["ntfy"] is True


@pytest.mark.asyncio
async def test_send_all_push_multiple(conn):
    push.configure_ntfy(conn, "topic")
    push.configure_pushover(conn, "api", "user")
    with patch("sentinel.push.send_ntfy", new_callable=AsyncMock, return_value=True):
        with patch("sentinel.push.send_pushover", new_callable=AsyncMock, return_value=True):
            result = await push.send_all_push(conn, "T", "M")
            assert "ntfy" in result
            assert "pushover" in result


@pytest.mark.asyncio
async def test_pushover_failure():
    with patch("sentinel.push.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("fail"))
        assert await push.send_pushover("api", "user", "T", "M") is False
