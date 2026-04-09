"""Tests for sentinel.budget."""
import pytest
import time
from sentinel import budget, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_set_budget(conn):
    bid = budget.set_budget(conn, "social", "daily", 1800)
    assert bid > 0


def test_get_budgets(conn):
    budget.set_budget(conn, "social", "daily", 1800)
    budget.set_budget(conn, "streaming", "weekly", 7200)
    assert len(budget.get_budgets(conn)) == 2


def test_get_budgets_empty(conn):
    assert budget.get_budgets(conn) == []


def test_get_budget_by_id(conn):
    bid = budget.set_budget(conn, "social", "daily", 1800)
    b = budget.get_budget(conn, bid)
    assert b["category"] == "social"


def test_get_budget_nonexistent(conn):
    assert budget.get_budget(conn, 999) is None


def test_delete_budget(conn):
    bid = budget.set_budget(conn, "test", "daily", 100)
    budget.delete_budget(conn, bid)
    assert budget.get_budgets(conn) == []


def test_check_budget_status_empty(conn):
    bid = budget.set_budget(conn, "social", "daily", 3600)
    status = budget.check_budget_status(conn, bid)
    assert status["used_seconds"] == 0
    assert status["exceeded"] is False


def test_check_budget_with_usage(conn):
    bid = budget.set_budget(conn, "social", "daily", 3600)
    db.save_seen(conn, "reddit.com", "social")
    # Insert activity today
    today_start = time.time() - 3600
    conn.execute(
        "INSERT INTO activity_log (ts, app, title, domain, duration_s) VALUES (?, 'x', '', 'reddit.com', 1800)",
        (today_start,))
    conn.commit()
    status = budget.check_budget_status(conn, bid)
    assert status["used_seconds"] == 1800


def test_exceeded_budget(conn):
    bid = budget.set_budget(conn, "social", "daily", 100)
    db.save_seen(conn, "x.com", "social")
    conn.execute(
        "INSERT INTO activity_log (ts, app, title, domain, duration_s) VALUES (?, 'x', '', 'x.com', 500)",
        (time.time(),))
    conn.commit()
    status = budget.check_budget_status(conn, bid)
    assert status["exceeded"] is True


def test_all_budgets_status(conn):
    budget.set_budget(conn, "social", "daily", 100)
    budget.set_budget(conn, "streaming", "daily", 200)
    all_status = budget.all_budgets_status(conn)
    assert len(all_status) == 2


def test_over_budget_empty(conn):
    assert budget.over_budget(conn) == []


def test_over_budget_with_data(conn):
    bid = budget.set_budget(conn, "social", "daily", 50)
    db.save_seen(conn, "x.com", "social")
    conn.execute(
        "INSERT INTO activity_log (ts, domain, duration_s) VALUES (?, 'x.com', 500)",
        (time.time(),))
    conn.commit()
    over = budget.over_budget(conn)
    assert len(over) >= 1


def test_period_start_daily():
    ts = budget._get_period_start_ts("daily")
    assert ts > 0


def test_period_start_weekly():
    ts = budget._get_period_start_ts("weekly")
    assert ts > 0


def test_period_start_monthly():
    ts = budget._get_period_start_ts("monthly")
    assert ts > 0
