"""Tests for sentinel.context."""
import pytest
from unittest.mock import patch, AsyncMock
from sentinel import context, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


@pytest.fixture(autouse=True)
def reset_cache():
    context._cache.clear()
    yield


def test_set_context(conn):
    context.set_current_context(conn, "Learning React")
    assert context.get_current_context(conn) == "Learning React"


def test_get_empty_context(conn):
    assert context.get_current_context(conn) == ""


def test_clear_context(conn):
    context.set_current_context(conn, "Something")
    context.clear_context(conn)
    assert context.get_current_context(conn) == ""


@pytest.mark.asyncio
async def test_classify_productive():
    with patch("sentinel.context.classifier.call_gemini", new_callable=AsyncMock,
               return_value="productive"):
        result = await context.classify_context("key", "youtube.com",
                                                 "React Tutorial", "/watch",
                                                 "Learning React")
        assert result == "productive"


@pytest.mark.asyncio
async def test_classify_distracting():
    with patch("sentinel.context.classifier.call_gemini", new_callable=AsyncMock,
               return_value="distracting"):
        result = await context.classify_context("key", "youtube.com",
                                                 "Funny Cats", "/watch",
                                                 "Writing a report")
        assert result == "distracting"


@pytest.mark.asyncio
async def test_classify_neutral():
    with patch("sentinel.context.classifier.call_gemini", new_callable=AsyncMock,
               return_value="neutral"):
        result = await context.classify_context("key", "example.com", "T", "/", "")
        assert result == "neutral"


@pytest.mark.asyncio
async def test_classify_invalid_response():
    with patch("sentinel.context.classifier.call_gemini", new_callable=AsyncMock,
               return_value="gibberish"):
        result = await context.classify_context("key", "example.com", "T", "/", "")
        assert result == "neutral"


@pytest.mark.asyncio
async def test_classify_caching():
    with patch("sentinel.context.classifier.call_gemini", new_callable=AsyncMock,
               return_value="productive") as mock:
        await context.classify_context("key", "d.com", "T1", "/", "goal")
        await context.classify_context("key", "d.com", "T1", "/", "goal")
        assert mock.call_count == 1  # Cached


@pytest.mark.asyncio
async def test_classify_different_contexts():
    with patch("sentinel.context.classifier.call_gemini", new_callable=AsyncMock,
               return_value="productive") as mock:
        await context.classify_context("key", "d.com", "T1", "/", "goal1")
        await context.classify_context("key", "d.com", "T1", "/", "goal2")
        assert mock.call_count == 2  # Different contexts


@pytest.mark.asyncio
async def test_classify_api_error():
    with patch("sentinel.context.classifier.call_gemini", new_callable=AsyncMock,
               side_effect=Exception("API down")):
        result = await context.classify_context("key", "d.com", "T", "/", "")
        assert result == "neutral"  # Safe default
