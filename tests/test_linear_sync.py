"""Tests for sentinel.linear_sync."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sentinel import linear_sync as ls, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_set_get_token(conn):
    ls.set_token(conn, "linear_api_xxx")
    assert ls.get_token(conn) == "linear_api_xxx"


def test_is_configured(conn):
    assert ls.is_configured(conn) is False
    ls.set_token(conn, "token")
    assert ls.is_configured(conn) is True


@pytest.mark.asyncio
async def test_get_issues_empty(conn):
    assert await ls.get_issues(conn) == []


@pytest.mark.asyncio
async def test_get_issues_success(conn):
    ls.set_token(conn, "token")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": {"issues": {"nodes": [{"id": "1", "title": "Test"}]}}
    }
    with patch("sentinel.linear_sync.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        issues = await ls.get_issues(conn)
        assert len(issues) == 1


@pytest.mark.asyncio
async def test_get_my_issues(conn):
    ls.set_token(conn, "token")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": {"viewer": {"assignedIssues": {"nodes": [{"id": "1"}]}}}
    }
    with patch("sentinel.linear_sync.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        issues = await ls.get_my_issues(conn)
        assert len(issues) == 1


@pytest.mark.asyncio
async def test_get_teams(conn):
    ls.set_token(conn, "token")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": {"teams": {"nodes": [{"id": "t1", "name": "Eng"}]}}}
    with patch("sentinel.linear_sync.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        teams = await ls.get_teams(conn)
        assert len(teams) == 1


@pytest.mark.asyncio
async def test_get_user(conn):
    ls.set_token(conn, "token")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": {"viewer": {"name": "Alice"}}}
    with patch("sentinel.linear_sync.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        user = await ls.get_user(conn)
        assert user["name"] == "Alice"


def test_clear_config(conn):
    ls.set_token(conn, "token")
    ls.clear_config(conn)
    assert ls.is_configured(conn) is False


@pytest.mark.asyncio
async def test_issue_count_empty(conn):
    assert await ls.issue_count(conn) == 0
