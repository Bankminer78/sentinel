"""Tests for sentinel.schedules_advanced."""
import pytest
from datetime import datetime, timedelta
from sentinel import schedules_advanced as sa, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_holiday(conn):
    hid = sa.add_holiday(conn, "Christmas", "2026-12-25")
    assert hid > 0


def test_get_holidays(conn):
    sa.add_holiday(conn, "Christmas", "2026-12-25")
    sa.add_holiday(conn, "NYE", "2026-12-31")
    holidays = sa.get_holidays(conn)
    assert len(holidays) == 2


def test_is_holiday_true(conn):
    sa.add_holiday(conn, "Test", "2026-04-09")
    assert sa.is_holiday(conn, "2026-04-09") is True


def test_is_holiday_false(conn):
    assert sa.is_holiday(conn, "2020-01-01") is False


def test_delete_holiday(conn):
    hid = sa.add_holiday(conn, "Test", "2026-04-09")
    sa.delete_holiday(conn, hid)
    assert sa.get_holidays(conn) == []


def test_add_exception(conn):
    eid = sa.add_exception(conn, 1, "2026-04-09", "skip")
    assert eid > 0


def test_is_exception_true(conn):
    sa.add_exception(conn, 1, "2026-04-09")
    assert sa.is_exception(conn, 1, "2026-04-09") is True


def test_is_exception_false(conn):
    assert sa.is_exception(conn, 1, "2026-04-09") is False


def test_exception_scoped_to_schedule(conn):
    sa.add_exception(conn, 1, "2026-04-09")
    assert sa.is_exception(conn, 2, "2026-04-09") is False


def test_get_exceptions_all(conn):
    sa.add_exception(conn, 1, "2026-04-09")
    sa.add_exception(conn, 2, "2026-04-10")
    all_ex = sa.get_exceptions(conn)
    assert len(all_ex) == 2


def test_get_exceptions_filtered(conn):
    sa.add_exception(conn, 1, "2026-04-09")
    sa.add_exception(conn, 2, "2026-04-10")
    filtered = sa.get_exceptions(conn, schedule_id=1)
    assert len(filtered) == 1


def test_delete_exception(conn):
    eid = sa.add_exception(conn, 1, "2026-04-09")
    sa.delete_exception(conn, eid)
    assert sa.get_exceptions(conn) == []


def test_next_n_days_schedule(conn):
    result = sa.next_n_days_schedule(conn, 1, n=3)
    assert len(result) == 3
    for day in result:
        assert "date" in day
        assert "active" in day
        assert "reason" in day


def test_next_n_days_with_holiday(conn):
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    sa.add_holiday(conn, "Holiday", tomorrow)
    result = sa.next_n_days_schedule(conn, 1, n=3)
    holiday_day = [d for d in result if d["date"] == tomorrow]
    assert holiday_day
    assert holiday_day[0]["active"] is False
    assert holiday_day[0]["reason"] == "holiday"


def test_holiday_replaces_existing(conn):
    sa.add_holiday(conn, "A", "2026-04-09")
    sa.add_holiday(conn, "B", "2026-04-09")  # Same date
    holidays = sa.get_holidays(conn)
    assert len(holidays) == 1  # REPLACE
