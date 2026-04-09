"""Tests for sentinel.points."""
import pytest
from sentinel import points, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_points(conn):
    points.add_points(conn, 10, "test")
    assert points.get_total_points(conn) == 10


def test_add_multiple_points(conn):
    points.add_points(conn, 10, "a")
    points.add_points(conn, 25, "b")
    assert points.get_total_points(conn) == 35


def test_empty_points(conn):
    assert points.get_total_points(conn) == 0


def test_level_for_points():
    assert points.level_for_points(0) == 1
    assert points.level_for_points(100) == 2
    assert points.level_for_points(400) == 3
    assert points.level_for_points(900) == 4


def test_level_for_points_negative():
    assert points.level_for_points(-100) == 1


def test_get_level_fresh(conn):
    level = points.get_level(conn)
    assert level["level"] == 1
    assert level["total_points"] == 0


def test_get_level_with_points(conn):
    points.add_points(conn, 150, "test")
    level = points.get_level(conn)
    assert level["level"] == 2
    assert level["total_points"] == 150


def test_get_level_progress(conn):
    points.add_points(conn, 200, "test")
    level = points.get_level(conn)
    assert 0 < level["progress_percent"] < 100


def test_points_for_action():
    assert points.points_for_action("completed_pomodoro") == 25
    assert points.points_for_action("focus_session") == 50
    assert points.points_for_action("achievement_unlocked") == 100
    assert points.points_for_action("unknown_action") == 0


def test_award(conn):
    total = points.award(conn, "completed_pomodoro")
    assert total == 25


def test_award_multiple(conn):
    points.award(conn, "completed_pomodoro")
    points.award(conn, "focus_session")
    assert points.get_total_points(conn) == 75


def test_award_unknown(conn):
    total = points.award(conn, "bogus_action")
    assert total == 0


def test_get_history(conn):
    points.add_points(conn, 10, "first")
    points.add_points(conn, 20, "second")
    hist = points.get_history(conn)
    assert len(hist) == 2


def test_get_history_limit(conn):
    for i in range(100):
        points.add_points(conn, 1, f"action_{i}")
    hist = points.get_history(conn, limit=10)
    assert len(hist) == 10


def test_history_order(conn):
    points.add_points(conn, 10, "first")
    points.add_points(conn, 20, "second")
    hist = points.get_history(conn)
    assert hist[0]["reason"] == "second"  # Most recent first


def test_points_for_level():
    assert points.points_for_level(1) == 0
    assert points.points_for_level(2) == 100
    assert points.points_for_level(3) == 400
