"""Tests for sentinel.writing_tracker."""
import pytest
from sentinel import writing_tracker as wt, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_project(conn):
    pid = wt.create_project(conn, "Novel", 50000)
    assert pid > 0


def test_get_projects(conn):
    wt.create_project(conn, "P1")
    wt.create_project(conn, "P2")
    assert len(wt.get_projects(conn)) == 2


def test_log_writing(conn):
    pid = wt.create_project(conn, "Test", 1000)
    wt.log_writing(conn, pid, 500, 30, "Good session")
    progress = wt.project_progress(conn, pid)
    assert progress["current_words"] == 500
    assert progress["percent"] == 50.0


def test_complete_project(conn):
    pid = wt.create_project(conn, "Test")
    wt.complete_project(conn, pid)
    assert len(wt.get_projects(conn, "active")) == 0
    assert len(wt.get_projects(conn, "complete")) == 1


def test_words_today_empty(conn):
    assert wt.words_today(conn) == 0


def test_words_today(conn):
    pid = wt.create_project(conn, "Test")
    wt.log_writing(conn, pid, 100)
    assert wt.words_today(conn) == 100


def test_words_this_week(conn):
    pid = wt.create_project(conn, "Test")
    wt.log_writing(conn, pid, 200)
    assert wt.words_this_week(conn) >= 200


def test_writing_streak_empty(conn):
    assert wt.writing_streak(conn) == 0


def test_writing_streak(conn):
    pid = wt.create_project(conn, "Test")
    wt.log_writing(conn, pid, 50)
    assert wt.writing_streak(conn) >= 1


def test_recent_sessions(conn):
    pid = wt.create_project(conn, "Test")
    for _ in range(3):
        wt.log_writing(conn, pid, 100)
    assert len(wt.recent_sessions(conn)) == 3


def test_avg_words_per_day(conn):
    pid = wt.create_project(conn, "Test")
    wt.log_writing(conn, pid, 300)
    avg = wt.avg_words_per_day(conn, days=30)
    assert avg == 10.0  # 300 / 30
