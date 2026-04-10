"""Tests for sentinel.privacy — one config key, three levels."""
import pytest
from pathlib import Path
from sentinel import privacy, db


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_default_level(conn):
    assert privacy.get_level(conn) == "balanced"


def test_set_minimal(conn):
    privacy.set_level(conn, "minimal")
    assert privacy.get_level(conn) == "minimal"


def test_set_full(conn):
    privacy.set_level(conn, "full")
    assert privacy.get_level(conn) == "full"


def test_set_invalid_raises(conn):
    with pytest.raises(ValueError):
        privacy.set_level(conn, "garbage")


def test_llm_allowed_only_above_minimal(conn):
    privacy.set_level(conn, "minimal")
    assert privacy.is_llm_allowed(conn) is False
    privacy.set_level(conn, "balanced")
    assert privacy.is_llm_allowed(conn) is True
    privacy.set_level(conn, "full")
    assert privacy.is_llm_allowed(conn) is True


def test_persists_across_get_calls(conn):
    privacy.set_level(conn, "full")
    assert privacy.get_level(conn) == "full"
    assert privacy.get_level(conn) == "full"
