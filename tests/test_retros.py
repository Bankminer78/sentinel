"""Tests for sentinel.retros."""
import pytest
from unittest.mock import patch, AsyncMock
from sentinel import retros, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_retro(conn):
    rid = retros.create_retro(conn, "2026-04-06", "Good week",
                               wins=["Shipped feature"], challenges=["Tired"], next_week=["Rest"])
    assert rid > 0


def test_get_retro(conn):
    retros.create_retro(conn, "2026-04-06", "Content", wins=["w1"])
    r = retros.get_retro(conn, "2026-04-06")
    assert r["content"] == "Content"
    assert r["wins"] == ["w1"]


def test_get_retro_nonexistent(conn):
    assert retros.get_retro(conn, "1999-01-01") is None


def test_list_retros(conn):
    retros.create_retro(conn, "2026-04-06", "R1")
    retros.create_retro(conn, "2026-04-13", "R2")
    assert len(retros.list_retros(conn)) == 2


def test_list_retros_limit(conn):
    for i in range(10):
        retros.create_retro(conn, f"2026-0{1 + i // 10}-0{i % 10 + 1}", f"R{i}")
    assert len(retros.list_retros(conn, limit=5)) == 5


def test_delete_retro(conn):
    rid = retros.create_retro(conn, "2026-04-06", "R")
    retros.delete_retro(conn, rid)
    assert retros.list_retros(conn) == []


def test_get_retro_by_id(conn):
    rid = retros.create_retro(conn, "2026-04-06", "R")
    r = retros.get_retro_by_id(conn, rid)
    assert r["content"] == "R"


def test_retro_default_week_start(conn):
    rid = retros.create_retro(conn, content="Test")
    r = retros.get_retro_by_id(conn, rid)
    assert r["week_start"]  # Auto-filled


def test_retro_with_empty_lists(conn):
    rid = retros.create_retro(conn, "2026-04-06", "")
    r = retros.get_retro_by_id(conn, rid)
    assert r["wins"] == []
    assert r["challenges"] == []
    assert r["next_week"] == []


@pytest.mark.asyncio
async def test_generate_retro_template(conn):
    with patch("sentinel.retros.classifier.call_gemini", new_callable=AsyncMock,
               return_value='{"wins": ["w1"], "challenges": ["c1"], "next_week": ["n1"]}'):
        result = await retros.generate_retro_template(conn, "key")
        assert result["wins"] == ["w1"]
        assert result["challenges"] == ["c1"]


@pytest.mark.asyncio
async def test_generate_retro_template_error(conn):
    with patch("sentinel.retros.classifier.call_gemini", new_callable=AsyncMock,
               side_effect=Exception("fail")):
        result = await retros.generate_retro_template(conn, "key")
        assert result["wins"] == []


def test_current_week_start():
    ws = retros._current_week_start()
    assert ws  # Returns a valid date string
