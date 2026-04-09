"""Tests for sentinel.notifications."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sentinel import notifications, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_notify_macos():
    with patch("sentinel.notifications.subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0)
        assert notifications.notify_macos("Title", "Message") is True
        assert mock.called


def test_notify_macos_with_subtitle():
    with patch("sentinel.notifications.subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0)
        notifications.notify_macos("T", "M", subtitle="S")
        args = mock.call_args[0][0]
        assert any("subtitle" in a for a in args)


def test_notify_macos_failure():
    with patch("sentinel.notifications.subprocess.run", side_effect=Exception("fail")):
        assert notifications.notify_macos("T", "M") is False


def test_notify_sound():
    with patch("sentinel.notifications.subprocess.run") as mock:
        notifications.notify_sound("Glass")
        assert mock.called


def test_notify_sound_custom():
    with patch("sentinel.notifications.subprocess.run") as mock:
        notifications.notify_sound("Ping")
        args = mock.call_args[0][0]
        assert any("Ping" in a for a in args)


@pytest.mark.asyncio
async def test_notify_webhook():
    with patch("sentinel.notifications.httpx.AsyncClient") as mock_client:
        mock_post = AsyncMock(return_value=MagicMock(status_code=200))
        mock_client.return_value.__aenter__.return_value.post = mock_post
        result = await notifications.notify_webhook("http://test.com", {"a": 1})
        assert result is True


@pytest.mark.asyncio
async def test_notify_webhook_failure():
    with patch("sentinel.notifications.httpx.AsyncClient") as mock_client:
        mock_post = AsyncMock(side_effect=Exception("fail"))
        mock_client.return_value.__aenter__.return_value.post = mock_post
        result = await notifications.notify_webhook("http://test.com", {})
        assert result is False


@pytest.mark.asyncio
async def test_notify_slack():
    with patch("sentinel.notifications.notify_webhook", new_callable=AsyncMock, return_value=True) as mock:
        result = await notifications.notify_slack("http://slack.com", "hello")
        assert result is True
        mock.assert_called_once()
        assert mock.call_args[0][1] == {"text": "hello"}


@pytest.mark.asyncio
async def test_notify_discord():
    with patch("sentinel.notifications.notify_webhook", new_callable=AsyncMock, return_value=True) as mock:
        result = await notifications.notify_discord("http://discord.com", "hey")
        assert result is True
        assert mock.call_args[0][1] == {"content": "hey"}


@pytest.mark.asyncio
async def test_send_all_macos(conn):
    with patch.object(notifications, "notify_macos", return_value=True):
        results = await notifications.send_all(conn, "T", "M", channels=["macos"])
        assert results["macos"] is True


@pytest.mark.asyncio
async def test_send_all_slack_no_config(conn):
    with patch.object(notifications, "notify_macos", return_value=True):
        results = await notifications.send_all(conn, "T", "M", channels=["slack"])
        assert results["slack"] is False  # No config


@pytest.mark.asyncio
async def test_send_all_slack_with_config(conn):
    db.set_config(conn, "slack_webhook", "http://slack.com")
    with patch.object(notifications, "notify_slack", new_callable=AsyncMock, return_value=True) as mock:
        results = await notifications.send_all(conn, "T", "M", channels=["slack"])
        assert results["slack"] is True
        mock.assert_called_once()


@pytest.mark.asyncio
async def test_send_all_default_channel(conn):
    with patch.object(notifications, "notify_macos", return_value=True):
        results = await notifications.send_all(conn, "T", "M")
        assert "macos" in results
