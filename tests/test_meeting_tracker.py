"""Tests for sentinel.meeting_tracker."""
import pytest
from sentinel import meeting_tracker as mt, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_log_meeting(conn):
    mid = mt.log_meeting(conn, "Standup", 15, "Alice, Bob", 7, "Follow up", "Good meeting")
    assert mid > 0


def test_get_meetings(conn):
    mt.log_meeting(conn, "M1", 30)
    mt.log_meeting(conn, "M2", 60)
    assert len(mt.get_meetings(conn)) == 2


def test_get_meeting(conn):
    mid = mt.log_meeting(conn, "Test", 30)
    m = mt.get_meeting(conn, mid)
    assert m["title"] == "Test"


def test_delete_meeting(conn):
    mid = mt.log_meeting(conn, "Delete", 30)
    mt.delete_meeting(conn, mid)
    assert mt.get_meeting(conn, mid) is None


def test_total_hours(conn):
    mt.log_meeting(conn, "M1", 60)
    mt.log_meeting(conn, "M2", 60)
    assert mt.total_meeting_hours(conn) == 2.0


def test_avg_effectiveness(conn):
    mt.log_meeting(conn, "M1", 30, effectiveness=8)
    mt.log_meeting(conn, "M2", 30, effectiveness=4)
    assert mt.avg_effectiveness(conn) == 6.0


def test_ineffective(conn):
    mt.log_meeting(conn, "Bad", 60, effectiveness=2)
    mt.log_meeting(conn, "Good", 60, effectiveness=9)
    bad = mt.ineffective_meetings(conn)
    assert len(bad) == 1


def test_meetings_by_day(conn):
    mt.log_meeting(conn, "M", 30)
    by_day = mt.meetings_by_day(conn)
    assert len(by_day) >= 1


def test_search(conn):
    mt.log_meeting(conn, "Standup", 15, notes="Discussed sprint")
    results = mt.search_meetings(conn, "sprint")
    assert len(results) == 1


def test_total_count(conn):
    mt.log_meeting(conn, "M1", 10)
    mt.log_meeting(conn, "M2", 20)
    assert mt.total_count(conn) == 2


def test_open_action_items(conn):
    mt.log_meeting(conn, "M", 30, action_items="Do X")
    items = mt.open_action_items(conn)
    assert len(items) == 1
