"""Tests for sentinel.inbox_zero."""
import pytest
from sentinel import inbox_zero as iz, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_log_count(conn):
    lid = iz.log_count(conn, "me@example.com", 10, 100)
    assert lid > 0


def test_current_count(conn):
    iz.log_count(conn, "me@ex.com", 5)
    c = iz.current_count(conn, "me@ex.com")
    assert c["unread"] == 5


def test_current_count_none(conn):
    assert iz.current_count(conn, "nonexistent") is None


def test_is_at_zero(conn):
    iz.log_count(conn, "me@ex.com", 0)
    assert iz.is_at_zero(conn, "me@ex.com") is True


def test_is_at_zero_false(conn):
    iz.log_count(conn, "me@ex.com", 5)
    assert iz.is_at_zero(conn, "me@ex.com") is False


def test_get_history(conn):
    iz.log_count(conn, "me@ex.com", 5)
    iz.log_count(conn, "me@ex.com", 3)
    history = iz.get_history(conn, "me@ex.com")
    assert len(history) == 2


def test_avg_unread(conn):
    iz.log_count(conn, "me@ex.com", 10)
    iz.log_count(conn, "me@ex.com", 20)
    assert iz.avg_unread(conn, "me@ex.com") == 15.0


def test_list_accounts(conn):
    iz.log_count(conn, "a@ex.com", 0)
    iz.log_count(conn, "b@ex.com", 0)
    assert len(iz.list_accounts(conn)) == 2


def test_times_at_zero(conn):
    iz.log_count(conn, "me@ex.com", 0)
    iz.log_count(conn, "me@ex.com", 5)
    iz.log_count(conn, "me@ex.com", 0)
    assert iz.times_at_zero(conn, "me@ex.com") == 2


def test_trend(conn):
    assert iz.trend(conn, "none") == "stable"
