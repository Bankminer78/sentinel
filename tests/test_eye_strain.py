"""Tests for sentinel.eye_strain."""
import pytest
import time
from sentinel import eye_strain as es, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_log_break(conn):
    lid = es.log_break(conn)
    assert lid > 0


def test_time_since_last_break_none(conn):
    assert es.time_since_last_break(conn) == float('inf')


def test_time_since_last_break(conn):
    es.log_break(conn)
    since = es.time_since_last_break(conn)
    assert since < 5  # Just logged


def test_is_break_due_true(conn):
    # No break logged
    assert es.is_break_due(conn) is True


def test_is_break_due_false(conn):
    es.log_break(conn)
    # Just logged, not due
    assert es.is_break_due(conn) is False


def test_get_breaks_today(conn):
    es.log_break(conn)
    es.log_break(conn)
    assert es.get_breaks_today(conn) == 2


def test_get_breaks_log(conn):
    es.log_break(conn)
    log = es.get_breaks_log(conn)
    assert len(log) == 1


def test_breaks_per_day_avg(conn):
    es.log_break(conn)
    avg = es.breaks_per_day_avg(conn, days=7)
    assert avg >= 0


def test_get_break_tip():
    tip = es.get_break_tip()
    assert tip
    assert len(tip) > 10


def test_should_notify_no_break(conn):
    assert es.should_notify(conn) is True


def test_should_notify_recent(conn):
    es.log_break(conn)
    assert es.should_notify(conn) is False


def test_custom_break_type(conn):
    es.log_break(conn, duration_s=60, break_type="long_rest")
    log = es.get_breaks_log(conn)
    assert log[0]["type"] == "long_rest"
