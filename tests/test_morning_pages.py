"""Tests for sentinel.morning_pages."""
import pytest
from sentinel import morning_pages as mp, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_write_pages(conn):
    result = mp.write_pages(conn, "Some text here " * 100)
    assert result["word_count"] == 300  # 100 * 3 words


def test_target_met(conn):
    text = "word " * 800
    result = mp.write_pages(conn, text)
    assert result["met"] is True


def test_target_not_met(conn):
    result = mp.write_pages(conn, "Short text")
    assert result["met"] is False


def test_get_pages(conn):
    mp.write_pages(conn, "Test content")
    pages = mp.get_pages(conn)
    assert pages["content"] == "Test content"


def test_list_recent(conn):
    mp.write_pages(conn, "Day 1 content")
    assert len(mp.list_recent(conn)) >= 1


def test_streak_empty(conn):
    assert mp.streak(conn) == 0


def test_streak_today(conn):
    mp.write_pages(conn, "word " * 200)  # 200 words > 100
    assert mp.streak(conn) >= 1


def test_total_words(conn):
    mp.write_pages(conn, "word " * 500)
    assert mp.total_words(conn) == 500


def test_avg_words(conn):
    mp.write_pages(conn, "word " * 500)
    assert mp.avg_words(conn) == 500.0


def test_target_met_days(conn):
    mp.write_pages(conn, "word " * 800)
    assert mp.target_met_days(conn) == 1


def test_search(conn):
    mp.write_pages(conn, "About my goals today")
    results = mp.search_pages(conn, "goals")
    assert len(results) == 1


def test_delete(conn):
    from datetime import datetime
    mp.write_pages(conn, "Delete this")
    today = datetime.now().strftime("%Y-%m-%d")
    mp.delete_pages(conn, today)
    assert mp.get_pages(conn, today) is None


def test_total_count(conn):
    mp.write_pages(conn, "content")
    assert mp.total_count(conn) == 1
