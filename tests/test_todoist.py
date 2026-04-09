"""Tests for sentinel.todoist."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sentinel import todoist, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_set_get_token(conn):
    todoist.set_token(conn, "abc123")
    assert todoist.get_token(conn) == "abc123"


def test_is_configured(conn):
    assert todoist.is_configured(conn) is False
    todoist.set_token(conn, "token")
    assert todoist.is_configured(conn) is True


@pytest.mark.asyncio
async def test_get_tasks_empty(conn):
    assert await todoist.get_tasks(conn) == []


@pytest.mark.asyncio
async def test_get_tasks_success(conn):
    todoist.set_token(conn, "token")
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = [{"id": "1", "content": "Task"}]
    with patch("sentinel.todoist.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        tasks = await todoist.get_tasks(conn)
        assert len(tasks) == 1


@pytest.mark.asyncio
async def test_create_task_not_configured(conn):
    result = await todoist.create_task(conn, "Test")
    assert "error" in result


@pytest.mark.asyncio
async def test_create_task_success(conn):
    todoist.set_token(conn, "token")
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"id": "task_123"}
    with patch("sentinel.todoist.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        result = await todoist.create_task(conn, "Buy milk")
        assert result.get("id") == "task_123"


@pytest.mark.asyncio
async def test_close_task(conn):
    todoist.set_token(conn, "token")
    mock_resp = MagicMock(status_code=204)
    with patch("sentinel.todoist.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        assert await todoist.close_task(conn, "123") is True


@pytest.mark.asyncio
async def test_close_task_not_configured(conn):
    assert await todoist.close_task(conn, "123") is False


@pytest.mark.asyncio
async def test_get_projects(conn):
    todoist.set_token(conn, "token")
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = [{"id": "p1"}, {"id": "p2"}]
    with patch("sentinel.todoist.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        projects = await todoist.get_projects(conn)
        assert len(projects) == 2


@pytest.mark.asyncio
async def test_delete_task(conn):
    todoist.set_token(conn, "token")
    mock_resp = MagicMock(status_code=204)
    with patch("sentinel.todoist.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.delete = AsyncMock(return_value=mock_resp)
        assert await todoist.delete_task(conn, "123") is True


def test_clear_config(conn):
    todoist.set_token(conn, "token")
    todoist.clear_config(conn)
    assert todoist.is_configured(conn) is False
