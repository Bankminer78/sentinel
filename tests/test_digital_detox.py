"""Tests for sentinel.digital_detox."""
import pytest
from sentinel import digital_detox as dd, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_list_programs():
    programs = dd.list_programs()
    assert len(programs) >= 5


def test_get_program():
    p = dd.get_program("24_hour")
    assert p is not None


def test_get_invalid_program():
    assert dd.get_program("nonexistent") is None


def test_start_detox(conn):
    sid = dd.start_detox(conn, "24_hour")
    assert sid > 0


def test_start_invalid(conn):
    assert dd.start_detox(conn, "invalid") == 0


def test_get_active_detox(conn):
    sid = dd.start_detox(conn, "24_hour")
    active = dd.get_active_detox(conn)
    assert active["id"] == sid


def test_complete_detox(conn):
    sid = dd.start_detox(conn, "24_hour")
    dd.complete_detox(conn, sid, "Great experience")
    assert dd.completed_detoxes(conn) == 1


def test_fail_detox(conn):
    sid = dd.start_detox(conn, "24_hour")
    dd.fail_detox(conn, sid)
    assert dd.get_active_detox(conn) is None


def test_total_programs():
    assert dd.total_programs() >= 5


def test_success_rate_empty(conn):
    assert dd.success_rate(conn) == 0


def test_success_rate(conn):
    sid1 = dd.start_detox(conn, "24_hour")
    sid2 = dd.start_detox(conn, "24_hour")
    dd.complete_detox(conn, sid1)
    assert dd.success_rate(conn) == 50.0
