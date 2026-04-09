"""Tests for sentinel.weekly_planner."""
import pytest
from sentinel import weekly_planner as wp, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_plan(conn):
    pid = wp.create_plan(conn, theme="Deep Work Week",
                          goals="Ship v1", big_three="A, B, C")
    assert pid > 0


def test_get_plan(conn):
    wp.create_plan(conn, theme="Test Week")
    plan = wp.current_plan(conn)
    assert plan["theme"] == "Test Week"


def test_list_plans(conn):
    wp.create_plan(conn, theme="W1", week_start="2026-04-01")
    wp.create_plan(conn, theme="W2", week_start="2026-04-08")
    assert len(wp.list_plans(conn)) == 2


def test_update_plan(conn):
    wp.create_plan(conn, week_start="2026-04-01", theme="Old")
    wp.update_plan(conn, "2026-04-01", theme="New")
    plan = wp.get_plan(conn, "2026-04-01")
    assert plan["theme"] == "New"


def test_delete_plan(conn):
    wp.create_plan(conn, week_start="2026-04-01")
    wp.delete_plan(conn, "2026-04-01")
    assert wp.get_plan(conn, "2026-04-01") is None


def test_search_plans(conn):
    wp.create_plan(conn, week_start="2026-04-01", theme="Deep Work")
    results = wp.search_plans(conn, "Deep")
    assert len(results) == 1


def test_total_plans(conn):
    wp.create_plan(conn, week_start="2026-04-01")
    wp.create_plan(conn, week_start="2026-04-08")
    assert wp.total_plans(conn) == 2


def test_has_plan_this_week_false(conn):
    assert wp.has_plan_this_week(conn) is False


def test_has_plan_this_week_true(conn):
    wp.create_plan(conn, theme="This week")
    assert wp.has_plan_this_week(conn) is True


def test_current_plan_none(conn):
    assert wp.current_plan(conn) is None
