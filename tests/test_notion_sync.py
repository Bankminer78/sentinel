"""Tests for sentinel.notion_sync."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sentinel import notion_sync as ns, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_set_get_config(conn):
    ns.set_config(conn, "token123", "db123")
    cfg = ns.get_config(conn)
    assert cfg["token"] == "token123"


def test_is_configured_false(conn):
    assert ns.is_configured(conn) is False


def test_is_configured_true(conn):
    ns.set_config(conn, "t", "d")
    assert ns.is_configured(conn) is True


def test_disable(conn):
    ns.set_config(conn, "t", "d")
    ns.disable(conn)
    assert ns.is_configured(conn) is False


@pytest.mark.asyncio
async def test_create_page_not_configured(conn):
    result = await ns.create_page(conn, "Test")
    assert "error" in result


@pytest.mark.asyncio
async def test_create_page_success(conn):
    ns.set_config(conn, "token", "db")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "page_123"}
    with patch("sentinel.notion_sync.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        result = await ns.create_page(conn, "Test", "Content")
        assert result == {"id": "page_123"}


@pytest.mark.asyncio
async def test_create_page_error(conn):
    ns.set_config(conn, "token", "db")
    with patch("sentinel.notion_sync.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("fail"))
        result = await ns.create_page(conn, "Test")
        assert "error" in result


@pytest.mark.asyncio
async def test_query_database_not_configured(conn):
    assert await ns.query_database(conn) == []


@pytest.mark.asyncio
async def test_query_database_success(conn):
    ns.set_config(conn, "token", "db")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": [{"id": "1"}, {"id": "2"}]}
    with patch("sentinel.notion_sync.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        results = await ns.query_database(conn)
        assert len(results) == 2


@pytest.mark.asyncio
async def test_sync_rules_empty(conn):
    assert await ns.sync_rules_to_notion(conn) == 0
