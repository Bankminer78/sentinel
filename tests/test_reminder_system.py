"""Tests for sentinel.reminder_system."""
import pytest
import time
from sentinel import reminder_system as rs, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_reminder(conn):
    rid = rs.create_reminder(conn, "Test", "Test message")
    assert rid > 0


def test_get_reminder(conn):
    rid = rs.create_reminder(conn, "Test", "msg")
    r = rs.get_reminder(conn, rid)
    assert r["title"] == "Test"


def test_list_reminders(conn):
    rs.create_reminder(conn, "R1")
    rs.create_reminder(conn, "R2")
    assert len(rs.list_reminders(conn)) == 2


def test_due_reminders(conn):
    past = time.time() - 100
    rs.create_reminder(conn, "Past", "msg", trigger_at=past)
    due = rs.due_reminders(conn)
    assert len(due) == 1


def test_mark_notified(conn):
    past = time.time() - 100
    rid = rs.create_reminder(conn, "Test", "msg", trigger_at=past)
    rs.mark_notified(conn, rid)
    assert len(rs.due_reminders(conn)) == 0


def test_mark_notified_recurring(conn):
    past = time.time() - 100
    rid = rs.create_reminder(conn, "Daily", "msg", trigger_at=past, recurring="daily")
    rs.mark_notified(conn, rid)
    # A new reminder should be created
    assert rs.total_reminders(conn) == 2


def test_delete_reminder(conn):
    rid = rs.create_reminder(conn, "Del")
    rs.delete_reminder(conn, rid)
    assert rs.total_reminders(conn) == 0


def test_reschedule(conn):
    rid = rs.create_reminder(conn, "Test")
    new_time = time.time() + 7200
    rs.reschedule(conn, rid, new_time)
    r = rs.get_reminder(conn, rid)
    assert r["notified"] == 0


def test_snooze(conn):
    rid = rs.create_reminder(conn, "Test")
    rs.snooze(conn, rid, 10)
    # Just verify no exception


def test_upcoming(conn):
    future = time.time() + 1800  # 30 min
    rs.create_reminder(conn, "Soon", trigger_at=future)
    upcoming = rs.upcoming(conn, hours=1)
    assert len(upcoming) == 1


def test_total_reminders(conn):
    rs.create_reminder(conn, "R1")
    rs.create_reminder(conn, "R2")
    assert rs.total_reminders(conn) == 2
