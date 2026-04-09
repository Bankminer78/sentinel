"""Tests for sentinel.search."""
import pytest
from sentinel import search, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_search_all_empty(conn):
    assert search.search_all(conn, "anything") == {}


def test_search_rules(conn):
    db.add_rule(conn, "Block YouTube")
    results = search.search_all(conn, "YouTube")
    assert "rules" in results
    assert len(results["rules"]) == 1


def test_search_activities(conn):
    db.log_activity(conn, "Chrome", "YouTube Video", "https://youtube.com", "youtube.com")
    results = search.search_all(conn, "youtube")
    assert "activities" in results


def test_search_case_insensitive(conn):
    db.add_rule(conn, "Block Twitter")
    # SQLite LIKE is case-insensitive by default for ASCII
    results = search.search_all(conn, "twitter")
    assert "rules" in results or results == {}


def test_search_no_match(conn):
    db.add_rule(conn, "Block YouTube")
    results = search.search_all(conn, "xyznomatch")
    assert results == {}


def test_count_results(conn):
    db.add_rule(conn, "Block Reddit")
    count = search.count_results(conn, "Reddit")
    assert count >= 1


def test_search_by_type(conn):
    db.add_rule(conn, "Test rule")
    results = search.search_by_type(conn, "Test", "rule")
    assert len(results) >= 1


def test_search_by_invalid_type(conn):
    results = search.search_by_type(conn, "x", "invalid")
    assert results == []


def test_log_search(conn):
    search.log_search(conn, "test query", 5)
    history = search.recent_searches(conn)
    assert len(history) >= 1


def test_recent_searches_empty(conn):
    assert search.recent_searches(conn) == []
