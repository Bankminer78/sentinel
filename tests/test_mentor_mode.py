"""Tests for sentinel.mentor_mode."""
import pytest
from sentinel import mentor_mode as mm, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_start_mentorship(conn):
    mid = mm.start_mentorship(conn, "Alice", "Bob", "Python")
    assert mid > 0


def test_get_mentorships(conn):
    mm.start_mentorship(conn, "Alice", "Bob")
    mm.start_mentorship(conn, "Carol", "Dave")
    assert len(mm.get_mentorships(conn)) == 2


def test_get_as_mentor(conn):
    mm.start_mentorship(conn, "Alice", "Bob")
    mm.start_mentorship(conn, "Alice", "Carol")
    assert len(mm.get_mentorships(conn, as_mentor="Alice")) == 2


def test_get_as_mentee(conn):
    mm.start_mentorship(conn, "Alice", "Bob")
    assert len(mm.get_mentorships(conn, as_mentee="Bob")) == 1


def test_end_mentorship(conn):
    mid = mm.start_mentorship(conn, "A", "B")
    mm.end_mentorship(conn, mid)
    assert len(mm.get_mentorships(conn)) == 0


def test_log_session(conn):
    mid = mm.start_mentorship(conn, "A", "B")
    sid = mm.log_session(conn, mid, "Discussed goals", "Do homework")
    assert sid > 0


def test_get_sessions(conn):
    mid = mm.start_mentorship(conn, "A", "B")
    mm.log_session(conn, mid, "Session 1")
    mm.log_session(conn, mid, "Session 2")
    assert len(mm.get_sessions(conn, mid)) == 2


def test_delete_session(conn):
    mid = mm.start_mentorship(conn, "A", "B")
    sid = mm.log_session(conn, mid, "Test")
    mm.delete_session(conn, sid)
    assert len(mm.get_sessions(conn, mid)) == 0


def test_mentorship_summary(conn):
    mid = mm.start_mentorship(conn, "A", "B", "Topic")
    mm.log_session(conn, mid, "S1")
    summary = mm.mentorship_summary(conn, mid)
    assert summary["session_count"] == 1


def test_summary_nonexistent(conn):
    assert mm.mentorship_summary(conn, 999) is None


def test_total_active(conn):
    mm.start_mentorship(conn, "A", "B")
    mm.start_mentorship(conn, "C", "D")
    assert mm.total_active(conn) == 2
