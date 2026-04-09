"""Tests for sentinel.meditation."""
import pytest
import time
from sentinel import meditation, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_list_sessions():
    sessions = meditation.list_sessions()
    assert len(sessions) >= 5
    assert all("id" in s and "name" in s for s in sessions)


def test_start_session(conn):
    sid = meditation.start_session(conn, "breathing_5min")
    assert sid > 0


def test_start_invalid(conn):
    assert meditation.start_session(conn, "nonexistent") == 0


def test_complete_session(conn):
    sid = meditation.start_session(conn, "breathing_5min")
    meditation.complete_session(conn, sid)
    logs = meditation.get_sessions_log(conn)
    assert logs[0]["completed"] == 1


def test_total_minutes_empty(conn):
    assert meditation.total_minutes(conn) == 0


def test_total_minutes_with_data(conn):
    sid = meditation.start_session(conn, "breathing_5min")
    # Backdate
    conn.execute("UPDATE meditation_log SET start_ts=?", (time.time() - 600,))
    conn.commit()
    meditation.complete_session(conn, sid)
    minutes = meditation.total_minutes(conn)
    assert minutes > 0


def test_sessions_log_empty(conn):
    assert meditation.get_sessions_log(conn) == []


def test_multiple_sessions(conn):
    meditation.start_session(conn, "breathing_5min")
    meditation.start_session(conn, "body_scan")
    assert len(meditation.get_sessions_log(conn)) == 2


def test_streak_no_sessions(conn):
    assert meditation.streak(conn) == 0


def test_streak_today(conn):
    sid = meditation.start_session(conn, "breathing_5min")
    meditation.complete_session(conn, sid)
    assert meditation.streak(conn) >= 1
