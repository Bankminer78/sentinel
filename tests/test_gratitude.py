"""Tests for sentinel.gratitude."""
import pytest
from datetime import datetime
from sentinel import gratitude, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_gratitude(conn):
    gid = gratitude.add_gratitude(conn, "Grateful for my family")
    assert gid > 0


def test_get_today_gratitudes(conn):
    gratitude.add_gratitude(conn, "Morning coffee")
    gratitude.add_gratitude(conn, "Good weather")
    today = gratitude.today_gratitudes(conn)
    assert len(today) == 2


def test_get_by_date(conn):
    gratitude.add_gratitude(conn, "2026 entry", "2026-04-09")
    entries = gratitude.get_gratitudes(conn, "2026-04-09")
    assert len(entries) == 1


def test_delete_gratitude(conn):
    gid = gratitude.add_gratitude(conn, "To delete")
    gratitude.delete_gratitude(conn, gid)
    assert gratitude.get_gratitudes(conn) == []


def test_gratitude_streak_zero(conn):
    assert gratitude.gratitude_streak(conn) == 0


def test_gratitude_streak_today(conn):
    gratitude.add_gratitude(conn, "Today's entry")
    assert gratitude.gratitude_streak(conn) >= 1


def test_search(conn):
    gratitude.add_gratitude(conn, "I love my family")
    gratitude.add_gratitude(conn, "Beautiful sunset")
    results = gratitude.search_gratitudes(conn, "family")
    assert len(results) == 1


def test_count(conn):
    for i in range(5):
        gratitude.add_gratitude(conn, f"Entry {i}")
    assert gratitude.count_gratitudes(conn) == 5


def test_random_gratitude_empty(conn):
    assert gratitude.random_gratitude(conn) is None


def test_random_gratitude(conn):
    gratitude.add_gratitude(conn, "Something")
    r = gratitude.random_gratitude(conn)
    assert r["text"] == "Something"


def test_empty(conn):
    assert gratitude.get_gratitudes(conn) == []
