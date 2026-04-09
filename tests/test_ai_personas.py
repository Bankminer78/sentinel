"""Tests for sentinel.ai_personas."""
import pytest
from sentinel import ai_personas, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_list_personas():
    personas = ai_personas.list_personas()
    assert len(personas) >= 5
    assert all("id" in p and "name" in p for p in personas)


def test_get_persona():
    p = ai_personas.get_persona("strict")
    assert p["name"] == "The Drill Sergeant"


def test_get_nonexistent_persona():
    assert ai_personas.get_persona("ghost") is None


def test_get_prompt_prefix():
    prefix = ai_personas.get_prompt_prefix("strict")
    assert "strict" in prefix.lower()


def test_set_current_persona(conn):
    assert ai_personas.set_current_persona(conn, "philosophical") is True
    assert ai_personas.get_current_persona(conn) == "philosophical"


def test_set_invalid_persona(conn):
    assert ai_personas.set_current_persona(conn, "invalid") is False


def test_default_persona(conn):
    assert ai_personas.get_current_persona(conn) == "supportive"


def test_get_current_persona_info(conn):
    ai_personas.set_current_persona(conn, "zen")
    info = ai_personas.get_current_persona_info(conn)
    assert info["id"] == "zen"
    assert "name" in info


def test_format_prompt_with_persona(conn):
    ai_personas.set_current_persona(conn, "supportive")
    formatted = ai_personas.format_prompt_with_persona(conn, "How am I doing?")
    assert "How am I doing?" in formatted


def test_all_personas_have_prefix():
    for pid in ai_personas.PERSONAS.keys():
        prefix = ai_personas.get_prompt_prefix(pid)
        assert prefix
