"""Tests for sentinel.environment — timezone, working hours, rest days, focus windows."""
import datetime as _dt
import pytest
from sentinel import environment


def _dt_on(weekday, hour, minute=0):
    # Pick a known Monday: 2024-01-01 is a Monday
    base = _dt.datetime(2024, 1, 1)
    return base + _dt.timedelta(days=weekday, hours=hour, minutes=minute)


class TestTimezone:
    def test_default_timezone_utc(self, conn):
        assert environment.get_timezone(conn) == "UTC"

    def test_set_and_get_timezone(self, conn):
        environment.set_timezone(conn, "America/New_York")
        assert environment.get_timezone(conn) == "America/New_York"

    def test_overwrite_timezone(self, conn):
        environment.set_timezone(conn, "America/New_York")
        environment.set_timezone(conn, "Europe/London")
        assert environment.get_timezone(conn) == "Europe/London"


class TestWorkingHours:
    def test_default_working_hours(self, conn):
        wh = environment.get_working_hours(conn)
        assert wh["start"] == "09:00"
        assert wh["end"] == "17:00"
        assert "monday" in wh["days"]

    def test_set_working_hours(self, conn):
        environment.set_working_hours(conn, "08:00", "16:00", ["monday", "tuesday"])
        wh = environment.get_working_hours(conn)
        assert wh["start"] == "08:00"
        assert wh["end"] == "16:00"
        assert wh["days"] == ["monday", "tuesday"]

    def test_is_working_hours_monday_10am(self, conn):
        assert environment.is_working_hours(conn, now=_dt_on(0, 10)) is True

    def test_is_working_hours_monday_8am_before(self, conn):
        assert environment.is_working_hours(conn, now=_dt_on(0, 8)) is False

    def test_is_working_hours_saturday(self, conn):
        assert environment.is_working_hours(conn, now=_dt_on(5, 10)) is False

    def test_is_working_hours_custom(self, conn):
        environment.set_working_hours(conn, "10:00", "14:00", ["monday"])
        assert environment.is_working_hours(conn, now=_dt_on(0, 11)) is True
        assert environment.is_working_hours(conn, now=_dt_on(0, 15)) is False


class TestRestDays:
    def test_default_rest_days(self, conn):
        assert environment.get_rest_days(conn) == ["saturday", "sunday"]

    def test_set_rest_days(self, conn):
        environment.set_rest_days(conn, ["friday", "saturday"])
        assert environment.get_rest_days(conn) == ["friday", "saturday"]

    def test_is_rest_day_saturday(self, conn):
        assert environment.is_rest_day(conn, now=_dt_on(5, 12)) is True

    def test_is_rest_day_monday(self, conn):
        assert environment.is_rest_day(conn, now=_dt_on(0, 12)) is False


class TestFocusWindow:
    def test_default_focus_window_none(self, conn):
        assert environment.get_focus_window(conn) is None

    def test_set_focus_window(self, conn):
        environment.set_focus_window(conn, "09:00", "11:00")
        fw = environment.get_focus_window(conn)
        assert fw["start"] == "09:00"

    def test_is_focus_window_inside(self, conn):
        environment.set_focus_window(conn, "09:00", "11:00")
        assert environment.is_focus_window(conn, now=_dt_on(0, 10)) is True

    def test_is_focus_window_outside(self, conn):
        environment.set_focus_window(conn, "09:00", "11:00")
        assert environment.is_focus_window(conn, now=_dt_on(0, 13)) is False

    def test_is_focus_window_none_returns_false(self, conn):
        assert environment.is_focus_window(conn) is False


class TestEnvironmentBundle:
    def test_get_environment_contains_all_keys(self, conn):
        env = environment.get_environment(conn)
        assert "timezone" in env
        assert "working_hours" in env
        assert "rest_days" in env
        assert "focus_window" in env

    def test_get_environment_after_set(self, conn):
        environment.set_timezone(conn, "Asia/Tokyo")
        environment.set_focus_window(conn, "06:00", "08:00")
        env = environment.get_environment(conn)
        assert env["timezone"] == "Asia/Tokyo"
        assert env["focus_window"]["start"] == "06:00"
