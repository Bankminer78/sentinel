"""Tests for sentinel.journal."""
import datetime as _dt
from sentinel import journal


def test_add_entry(conn):
    eid = journal.add_entry(conn, "Today was good")
    assert eid > 0


def test_add_entry_with_mood(conn):
    eid = journal.add_entry(conn, "ok", mood=7)
    e = journal.get_entry_by_id(conn, eid)
    assert e["mood"] == 7


def test_add_entry_with_tags(conn):
    eid = journal.add_entry(conn, "note", tags=["work", "happy"])
    e = journal.get_entry_by_id(conn, eid)
    assert e["tags"] == ["work", "happy"]


def test_get_entries_empty(conn):
    assert journal.get_entries(conn) == []


def test_get_entries(conn):
    journal.add_entry(conn, "a")
    journal.add_entry(conn, "b")
    assert len(journal.get_entries(conn)) == 2


def test_get_entries_limit(conn):
    for i in range(5):
        journal.add_entry(conn, f"entry {i}")
    assert len(journal.get_entries(conn, limit=3)) == 3


def test_get_entry_by_id(conn):
    eid = journal.add_entry(conn, "hello")
    e = journal.get_entry_by_id(conn, eid)
    assert e["content"] == "hello"


def test_get_entry_nonexistent(conn):
    assert journal.get_entry_by_id(conn, 9999) is None


def test_delete_entry(conn):
    eid = journal.add_entry(conn, "bye")
    journal.delete_entry(conn, eid)
    assert journal.get_entry_by_id(conn, eid) is None


def test_today_entry(conn):
    journal.add_entry(conn, "today")
    e = journal.get_today_entry(conn)
    assert e["content"] == "today"


def test_today_entry_none(conn):
    assert journal.get_today_entry(conn) is None


def test_search_entries(conn):
    journal.add_entry(conn, "loved the weather")
    journal.add_entry(conn, "bad day")
    results = journal.search_entries(conn, "weather")
    assert len(results) == 1


def test_search_no_match(conn):
    journal.add_entry(conn, "hello")
    assert journal.search_entries(conn, "xyz") == []


def test_mood_trend(conn):
    journal.add_entry(conn, "a", mood=5)
    journal.add_entry(conn, "b", mood=7)
    trend = journal.get_mood_trend(conn, days=30)
    assert len(trend) == 1
    assert trend[0]["avg_mood"] == 6.0


def test_mood_trend_ignores_null(conn):
    journal.add_entry(conn, "a", mood=5)
    journal.add_entry(conn, "no mood")
    trend = journal.get_mood_trend(conn)
    assert trend[0]["avg_mood"] == 5.0


def test_tags_default_empty(conn):
    eid = journal.add_entry(conn, "nothing")
    e = journal.get_entry_by_id(conn, eid)
    assert e["tags"] == []
