"""Tests for sentinel.tracker."""
import pytest
import time
from sentinel import tracker, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_start_tracking(conn):
    sid = tracker.start_tracking(conn, "work")
    assert sid > 0


def test_active_tracking(conn):
    tracker.start_tracking(conn, "work", "writing code")
    active = tracker.get_active_tracking(conn)
    assert active is not None
    assert active["project"] == "work"


def test_no_active_tracking(conn):
    assert tracker.get_active_tracking(conn) is None


def test_stop_tracking(conn):
    sid = tracker.start_tracking(conn, "work")
    result = tracker.stop_tracking(conn, sid)
    assert result is not None
    assert result["end_ts"] is not None


def test_stop_without_id(conn):
    tracker.start_tracking(conn, "work")
    result = tracker.stop_tracking(conn)
    assert result is not None


def test_stop_nothing_active(conn):
    result = tracker.stop_tracking(conn)
    assert result is None


def test_auto_stop_on_new_start(conn):
    sid1 = tracker.start_tracking(conn, "work")
    sid2 = tracker.start_tracking(conn, "personal")
    active = tracker.get_active_tracking(conn)
    assert active["id"] == sid2
    # Old session should be stopped
    r = conn.execute("SELECT end_ts FROM time_entries WHERE id=?", (sid1,)).fetchone()
    assert r["end_ts"] is not None


def test_get_tracked_time_empty(conn):
    assert tracker.get_tracked_time(conn) == {}


def test_get_tracked_time_with_data(conn):
    sid = tracker.start_tracking(conn, "work")
    time.sleep(0.01)
    tracker.stop_tracking(conn, sid)
    result = tracker.get_tracked_time(conn)
    assert "work" in result
    assert result["work"] > 0


def test_get_tracked_time_by_project(conn):
    sid1 = tracker.start_tracking(conn, "work")
    tracker.stop_tracking(conn, sid1)
    sid2 = tracker.start_tracking(conn, "personal")
    tracker.stop_tracking(conn, sid2)
    result = tracker.get_tracked_time(conn, project="work")
    assert "work" in result
    assert "personal" not in result


def test_list_projects_empty(conn):
    assert tracker.list_projects(conn) == []


def test_list_projects(conn):
    tracker.start_tracking(conn, "work")
    tracker.stop_tracking(conn)
    tracker.start_tracking(conn, "personal")
    tracker.stop_tracking(conn)
    result = tracker.list_projects(conn)
    assert len(result) == 2
    projects = [p["project"] for p in result]
    assert "work" in projects
    assert "personal" in projects


def test_tracking_with_description(conn):
    sid = tracker.start_tracking(conn, "work", "fixing bug")
    active = tracker.get_active_tracking(conn)
    assert active["description"] == "fixing bug"


def test_multiple_sessions_same_project(conn):
    for i in range(3):
        sid = tracker.start_tracking(conn, "work")
        tracker.stop_tracking(conn, sid)
    result = tracker.list_projects(conn)
    work = [p for p in result if p["project"] == "work"][0]
    assert work["sessions"] == 3


def test_tracker_duration_calc(conn):
    sid = tracker.start_tracking(conn, "test")
    time.sleep(0.02)
    result = tracker.stop_tracking(conn, sid)
    assert result["duration_s"] >= 0.01
