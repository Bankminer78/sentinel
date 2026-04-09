"""Tests for sentinel.timebox."""
import pytest
import time
from sentinel import timebox, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_timebox(conn):
    tid = timebox.create_timebox(conn, "Write email", 15)
    assert tid > 0


def test_start_timebox(conn):
    tid = timebox.create_timebox(conn, "Test", 30)
    timebox.start_timebox(conn, tid)
    box = timebox.get_timebox(conn, tid)
    assert box["start_ts"] is not None


def test_end_timebox(conn):
    tid = timebox.create_timebox(conn, "Test", 30)
    timebox.start_timebox(conn, tid)
    time.sleep(0.01)
    timebox.end_timebox(conn, tid)
    box = timebox.get_timebox(conn, tid)
    assert box["end_ts"] is not None
    assert box["completed"] == 1


def test_end_not_started(conn):
    tid = timebox.create_timebox(conn, "Test", 30)
    timebox.end_timebox(conn, tid, completed=False)
    box = timebox.get_timebox(conn, tid)
    assert box["completed"] == 0


def test_list_timeboxes(conn):
    tid = timebox.create_timebox(conn, "T1", 30)
    timebox.start_timebox(conn, tid)
    assert len(timebox.list_timeboxes(conn)) == 1


def test_active_timebox(conn):
    tid = timebox.create_timebox(conn, "Test", 30)
    timebox.start_timebox(conn, tid)
    active = timebox.active_timebox(conn)
    assert active["id"] == tid


def test_no_active(conn):
    assert timebox.active_timebox(conn) is None


def test_delete(conn):
    tid = timebox.create_timebox(conn, "Delete", 10)
    timebox.delete_timebox(conn, tid)
    assert timebox.get_timebox(conn, tid) is None


def test_estimate_accuracy_empty(conn):
    assert timebox.estimate_accuracy(conn) == 0


def test_completion_rate_empty(conn):
    assert timebox.completion_rate(conn) == 0


def test_completion_rate(conn):
    tid1 = timebox.create_timebox(conn, "T1", 10)
    tid2 = timebox.create_timebox(conn, "T2", 10)
    timebox.start_timebox(conn, tid1)
    timebox.start_timebox(conn, tid2)
    timebox.end_timebox(conn, tid1, completed=True)
    timebox.end_timebox(conn, tid2, completed=False)
    rate = timebox.completion_rate(conn)
    assert rate == 50.0
