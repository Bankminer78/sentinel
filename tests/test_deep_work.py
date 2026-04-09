"""Tests for sentinel.deep_work."""
import pytest
import time
from sentinel import deep_work as dw, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_start_deep_work(conn):
    sid = dw.start_deep_work(conn, "project-a")
    assert sid > 0


def test_get_active_session(conn):
    sid = dw.start_deep_work(conn, "test")
    active = dw.get_active_session(conn)
    assert active["id"] == sid


def test_no_active_session(conn):
    assert dw.get_active_session(conn) is None


def test_end_deep_work(conn):
    sid = dw.start_deep_work(conn, "test")
    time.sleep(0.01)
    result = dw.end_deep_work(conn, sid, quality=8, notes="Great session")
    assert result["quality"] == 8


def test_total_hours_empty(conn):
    assert dw.total_hours(conn) == 0.0


def test_total_hours_with_data(conn):
    sid = dw.start_deep_work(conn)
    # Backdate and manually set end
    conn.execute("UPDATE deep_work_sessions SET start_ts=?, end_ts=?",
                 (time.time() - 3600, time.time()))
    conn.commit()
    hours = dw.total_hours(conn, days=7)
    assert hours > 0


def test_get_sessions_empty(conn):
    assert dw.get_sessions(conn) == []


def test_get_sessions(conn):
    dw.start_deep_work(conn, "p1")
    dw.start_deep_work(conn, "p2")
    assert len(dw.get_sessions(conn)) == 2


def test_avg_session_length_empty(conn):
    assert dw.avg_session_length(conn) == 0.0


def test_longest_session_empty(conn):
    assert dw.longest_session(conn) == 0.0


def test_quality_average_empty(conn):
    assert dw.quality_average(conn) == 0


def test_quality_average(conn):
    sid = dw.start_deep_work(conn)
    dw.end_deep_work(conn, sid, quality=9)
    assert dw.quality_average(conn) == 9.0


def test_by_project_empty(conn):
    assert dw.by_project(conn) == {}


def test_by_project_with_data(conn):
    sid = dw.start_deep_work(conn, "myproject")
    dw.end_deep_work(conn, sid)
    result = dw.by_project(conn)
    assert "myproject" in result
