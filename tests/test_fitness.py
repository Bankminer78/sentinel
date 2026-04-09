"""Tests for sentinel.fitness."""
import pytest
from sentinel import fitness, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_log_workout(conn):
    wid = fitness.log_workout(conn, "Morning Run", "cardio", 30, 300)
    assert wid > 0


def test_get_workouts(conn):
    fitness.log_workout(conn, "W1")
    fitness.log_workout(conn, "W2")
    assert len(fitness.get_workouts(conn)) == 2


def test_log_exercise(conn):
    wid = fitness.log_workout(conn, "Upper body")
    eid = fitness.log_exercise(conn, wid, "Bench Press", 5, 5, 100)
    assert eid > 0


def test_get_exercises(conn):
    wid = fitness.log_workout(conn, "Test")
    fitness.log_exercise(conn, wid, "Squat", 3, 10, 80)
    fitness.log_exercise(conn, wid, "Deadlift", 3, 5, 120)
    assert len(fitness.get_exercises(conn, wid)) == 2


def test_total_workouts(conn):
    fitness.log_workout(conn, "W1")
    fitness.log_workout(conn, "W2")
    assert fitness.total_workouts(conn) == 2


def test_total_calories(conn):
    fitness.log_workout(conn, "Run", calories=300)
    fitness.log_workout(conn, "Bike", calories=200)
    assert fitness.total_calories(conn) == 500


def test_total_duration(conn):
    fitness.log_workout(conn, "Run", duration_min=30)
    fitness.log_workout(conn, "Bike", duration_min=45)
    assert fitness.total_duration(conn) == 75


def test_check_pr_new(conn):
    assert fitness.check_pr(conn, "Bench", 100) is True


def test_check_pr_higher(conn):
    fitness.check_pr(conn, "Bench", 100)
    assert fitness.check_pr(conn, "Bench", 110) is True


def test_check_pr_lower(conn):
    fitness.check_pr(conn, "Bench", 100)
    assert fitness.check_pr(conn, "Bench", 90) is False


def test_get_prs(conn):
    fitness.check_pr(conn, "Squat", 200)
    fitness.check_pr(conn, "Bench", 100)
    prs = fitness.get_prs(conn)
    assert len(prs) == 2


def test_workout_streak(conn):
    fitness.log_workout(conn, "Today")
    assert fitness.workout_streak(conn) >= 1


def test_by_type(conn):
    fitness.log_workout(conn, "Run", "cardio")
    fitness.log_workout(conn, "Lift", "strength")
    by_t = fitness.by_type(conn)
    assert "cardio" in by_t
