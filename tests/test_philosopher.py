"""Tests for sentinel.philosopher."""
import pytest
from sentinel import philosopher, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_random_quote():
    quote, author = philosopher.random_quote()
    assert quote
    assert author


def test_daily_quote_consistent():
    """Daily quote should be the same throughout the day."""
    q1 = philosopher.daily_quote()
    q2 = philosopher.daily_quote()
    assert q1 == q2


def test_morning_prompt():
    prompt = philosopher.morning_prompt()
    assert prompt.endswith("?")


def test_evening_prompt():
    prompt = philosopher.evening_prompt()
    assert prompt.endswith("?")


def test_save_reflection(conn):
    rid = philosopher.save_reflection(conn, "What went well?", "Finished the PR")
    assert rid > 0


def test_get_reflections(conn):
    philosopher.save_reflection(conn, "p1", "r1")
    philosopher.save_reflection(conn, "p2", "r2")
    reflections = philosopher.get_reflections(conn)
    assert len(reflections) == 2


def test_search_reflections(conn):
    philosopher.save_reflection(conn, "Morning prompt", "I am grateful for my health")
    philosopher.save_reflection(conn, "Evening prompt", "I was distracted today")
    results = philosopher.search_reflections(conn, "grateful")
    assert len(results) == 1


def test_search_no_match(conn):
    philosopher.save_reflection(conn, "test", "nothing here")
    assert philosopher.search_reflections(conn, "xyzzy") == []


def test_empty_reflections(conn):
    assert philosopher.get_reflections(conn) == []


def test_quote_list_has_many():
    assert len(philosopher.STOIC_QUOTES) >= 10


def test_quotes_have_authors():
    for quote, author in philosopher.STOIC_QUOTES:
        assert quote
        assert author
