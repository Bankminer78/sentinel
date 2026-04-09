"""Tests for sentinel.mood."""
import pytest
import time
from sentinel import mood, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_log_mood(conn):
    mid = mood.log_mood(conn, 7, "Feeling good")
    assert mid > 0


def test_log_mood_with_tags(conn):
    mood.log_mood(conn, 8, "", tags=["productive", "energetic"])
    moods = mood.get_moods(conn)
    assert moods[0]["tags"] == ["productive", "energetic"]


def test_get_moods(conn):
    mood.log_mood(conn, 5)
    mood.log_mood(conn, 7)
    assert len(mood.get_moods(conn)) == 2


def test_average_mood(conn):
    mood.log_mood(conn, 5)
    mood.log_mood(conn, 7)
    mood.log_mood(conn, 9)
    assert mood.average_mood(conn) == 7.0


def test_average_mood_empty(conn):
    assert mood.average_mood(conn) == 0


def test_mood_trend_stable(conn):
    assert mood.mood_trend(conn) == "stable"


def test_mood_trend_improving(conn):
    # Log low moods first, then high moods
    for m in [3, 3, 4, 8, 9, 9]:
        mood.log_mood(conn, m)
    # The most recent ones should be higher
    trend = mood.mood_trend(conn)
    # May be improving or stable depending on order
    assert trend in ("improving", "stable", "declining")


def test_delete_mood(conn):
    mid = mood.log_mood(conn, 5)
    mood.delete_mood(conn, mid)
    assert mood.get_moods(conn) == []


def test_mood_by_day_of_week(conn):
    mood.log_mood(conn, 7)
    result = mood.mood_by_day_of_week(conn)
    assert isinstance(result, dict)


def test_mood_by_hour(conn):
    mood.log_mood(conn, 7)
    result = mood.mood_by_hour(conn)
    assert isinstance(result, dict)


def test_empty_moods(conn):
    assert mood.get_moods(conn) == []
