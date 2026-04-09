"""Tests for sentinel.daily_planner."""
import pytest
from sentinel import daily_planner as dp, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_plan(conn):
    pid = dp.create_plan(conn, "2026-04-09", "Work on project", "Top 3 tasks")
    assert pid > 0


def test_get_plan(conn):
    dp.create_plan(conn, "2026-04-09", "Goals", "Priorities")
    plan = dp.get_plan(conn, "2026-04-09")
    assert plan["goals"] == "Goals"


def test_add_block(conn):
    pid = dp.create_plan(conn, "2026-04-09")
    bid = dp.add_block(conn, pid, "09:00", "10:00", "Email")
    assert bid > 0


def test_complete_block(conn):
    pid = dp.create_plan(conn, "2026-04-09")
    bid = dp.add_block(conn, pid, "09:00", "10:00", "Email")
    dp.complete_block(conn, bid)
    plan = dp.get_plan(conn, "2026-04-09")
    assert plan["blocks"][0]["completed"] == 1


def test_delete_block(conn):
    pid = dp.create_plan(conn, "2026-04-09")
    bid = dp.add_block(conn, pid, "09:00", "10:00", "Email")
    dp.delete_block(conn, bid)
    plan = dp.get_plan(conn, "2026-04-09")
    assert len(plan["blocks"]) == 0


def test_list_plans(conn):
    dp.create_plan(conn, "2026-04-09")
    dp.create_plan(conn, "2026-04-08")
    assert len(dp.list_plans(conn)) == 2


def test_plan_completion(conn):
    pid = dp.create_plan(conn, "2026-04-09")
    b1 = dp.add_block(conn, pid, "09:00", "10:00", "A")
    b2 = dp.add_block(conn, pid, "10:00", "11:00", "B")
    dp.complete_block(conn, b1)
    assert dp.plan_completion(conn, "2026-04-09") == 50.0


def test_update_plan(conn):
    dp.create_plan(conn, "2026-04-09", "old goals")
    dp.update_plan(conn, "2026-04-09", goals="new goals")
    plan = dp.get_plan(conn, "2026-04-09")
    assert plan["goals"] == "new goals"


def test_completion_trend_empty(conn):
    assert dp.completion_trend(conn) == 0


def test_get_nonexistent_plan(conn):
    assert dp.get_plan(conn, "1999-01-01") is None
