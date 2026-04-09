"""Tests for sentinel.nutrition."""
import pytest
from sentinel import nutrition, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_log_meal(conn):
    mid = nutrition.log_meal(conn, "Breakfast", 500, 30, 60, 15)
    assert mid > 0


def test_get_meals(conn):
    nutrition.log_meal(conn, "M1", 300)
    nutrition.log_meal(conn, "M2", 400)
    assert len(nutrition.get_meals(conn)) == 2


def test_today_meals(conn):
    nutrition.log_meal(conn, "Lunch", 600)
    assert len(nutrition.today_meals(conn)) == 1


def test_today_totals(conn):
    nutrition.log_meal(conn, "M1", 500, 30, 50, 20)
    nutrition.log_meal(conn, "M2", 400, 25, 40, 15)
    totals = nutrition.today_totals(conn)
    assert totals["calories"] == 900
    assert totals["protein_g"] == 55


def test_set_goals(conn):
    nutrition.set_goals(conn, 2000, 150, 200, 60)
    goals = nutrition.get_goals(conn)
    assert goals["calories"] == 2000


def test_goal_progress_no_goals(conn):
    assert nutrition.goal_progress(conn) is None


def test_goal_progress_with_goals(conn):
    nutrition.set_goals(conn, 2000, 150, 200, 60)
    nutrition.log_meal(conn, "Meal", 1000, 75, 100, 30)
    progress = nutrition.goal_progress(conn)
    assert progress["calories"]["percent"] == 50.0


def test_delete_meal(conn):
    mid = nutrition.log_meal(conn, "Delete", 100)
    nutrition.delete_meal(conn, mid)
    assert nutrition.get_meals(conn) == []


def test_weekly_avg_empty(conn):
    assert nutrition.weekly_avg_calories(conn) == 0


def test_weekly_avg(conn):
    nutrition.log_meal(conn, "Meal", 2000)
    avg = nutrition.weekly_avg_calories(conn)
    assert avg == 2000.0  # Single day with 2000
