"""Tests for sentinel.money_tracker."""
import pytest
from sentinel import money_tracker as mt, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_log_expense(conn):
    eid = mt.log_expense(conn, 25.50, "food", "Lunch")
    assert eid > 0


def test_get_expenses(conn):
    mt.log_expense(conn, 10, "food")
    mt.log_expense(conn, 20, "transport")
    assert len(mt.get_expenses(conn)) == 2


def test_get_expenses_by_category(conn):
    mt.log_expense(conn, 10, "food")
    mt.log_expense(conn, 20, "transport")
    food = mt.get_expenses(conn, category="food")
    assert len(food) == 1


def test_total_spent(conn):
    mt.log_expense(conn, 10, "food")
    mt.log_expense(conn, 20, "food")
    assert mt.total_spent(conn) == 30.0


def test_spending_by_category(conn):
    mt.log_expense(conn, 10, "food")
    mt.log_expense(conn, 20, "transport")
    by_cat = mt.spending_by_category(conn)
    assert by_cat["food"] == 10
    assert by_cat["transport"] == 20


def test_set_budget(conn):
    bid = mt.set_budget(conn, "food", 300)
    assert bid > 0


def test_get_budgets(conn):
    mt.set_budget(conn, "food", 300)
    mt.set_budget(conn, "transport", 100)
    assert len(mt.get_budgets(conn)) == 2


def test_budget_status(conn):
    mt.set_budget(conn, "food", 100)
    mt.log_expense(conn, 50, "food")
    status = mt.budget_status(conn, "food")
    assert status["spent"] == 50
    assert status["remaining"] == 50


def test_budget_exceeded(conn):
    mt.set_budget(conn, "food", 50)
    mt.log_expense(conn, 100, "food")
    status = mt.budget_status(conn, "food")
    assert status["exceeded"] is True


def test_delete_expense(conn):
    eid = mt.log_expense(conn, 10, "food")
    mt.delete_expense(conn, eid)
    assert mt.get_expenses(conn) == []


def test_biggest_expenses(conn):
    mt.log_expense(conn, 10, "food")
    mt.log_expense(conn, 100, "rent")
    mt.log_expense(conn, 50, "shopping")
    big = mt.biggest_expenses(conn, limit=2)
    assert big[0]["amount"] == 100


def test_budget_nonexistent(conn):
    assert mt.budget_status(conn, "nonexistent") is None
