"""Tests for sentinel.scheduler — time rules, pomodoro, allowances, focus sessions."""

import datetime as dt

import pytest

from sentinel import scheduler


# ---------------------------------------------------------------------------
# parse_days
# ---------------------------------------------------------------------------


class TestParseDays:
    def test_all(self):
        assert scheduler.parse_days("all") == {0, 1, 2, 3, 4, 5, 6}

    def test_empty_is_all(self):
        assert scheduler.parse_days("") == {0, 1, 2, 3, 4, 5, 6}

    def test_mon_fri_range(self):
        assert scheduler.parse_days("mon-fri") == {0, 1, 2, 3, 4}

    def test_sat_sun_range(self):
        assert scheduler.parse_days("sat-sun") == {5, 6}

    def test_list_full_names(self):
        assert scheduler.parse_days(["monday", "friday"]) == {0, 4}

    def test_list_short_names(self):
        assert scheduler.parse_days(["mon", "wed", "fri"]) == {0, 2, 4}

    def test_comma_separated(self):
        assert scheduler.parse_days("mon,wed,fri") == {0, 2, 4}

    def test_wrapping_range_fri_mon(self):
        # Fri -> Mon wraps around through weekend
        assert scheduler.parse_days("fri-mon") == {4, 5, 6, 0}

    def test_invalid_day_ignored(self):
        assert scheduler.parse_days(["monday", "notaday"]) == {0}

    def test_case_insensitive(self):
        assert scheduler.parse_days("MON-FRI") == {0, 1, 2, 3, 4}


# ---------------------------------------------------------------------------
# is_schedule_active
# ---------------------------------------------------------------------------


class TestIsScheduleActive:
    def test_weekday_in_window(self):
        # 2026-04-08 is a Wednesday (weekday 2)
        now = dt.datetime(2026, 4, 8, 10, 0)
        sched = {"days": "mon-fri", "start": "09:00", "end": "17:00"}
        assert scheduler.is_schedule_active(sched, now) is True

    def test_weekday_before_window(self):
        now = dt.datetime(2026, 4, 8, 8, 0)
        sched = {"days": "mon-fri", "start": "09:00", "end": "17:00"}
        assert scheduler.is_schedule_active(sched, now) is False

    def test_weekday_after_window(self):
        now = dt.datetime(2026, 4, 8, 18, 0)
        sched = {"days": "mon-fri", "start": "09:00", "end": "17:00"}
        assert scheduler.is_schedule_active(sched, now) is False

    def test_saturday_not_in_weekday_schedule(self):
        # 2026-04-11 is Saturday
        now = dt.datetime(2026, 4, 11, 10, 0)
        sched = {"days": "mon-fri", "start": "09:00", "end": "17:00"}
        assert scheduler.is_schedule_active(sched, now) is False

    def test_weekend_schedule_saturday(self):
        now = dt.datetime(2026, 4, 11, 10, 0)
        sched = {"days": "sat-sun", "start": "00:00", "end": "23:59"}
        assert scheduler.is_schedule_active(sched, now) is True

    def test_weekend_schedule_weekday_false(self):
        now = dt.datetime(2026, 4, 8, 10, 0)
        sched = {"days": "sat-sun", "start": "00:00", "end": "23:59"}
        assert scheduler.is_schedule_active(sched, now) is False

    def test_midnight_crossing_active_late_night(self):
        # Wed 23:30 — schedule is 22:00-02:00 on Wed
        now = dt.datetime(2026, 4, 8, 23, 30)
        sched = {"days": "wed", "start": "22:00", "end": "02:00"}
        assert scheduler.is_schedule_active(sched, now) is True

    def test_midnight_crossing_active_early_morning(self):
        # Thu 01:00 — schedule started Wed night, active until 02:00
        now = dt.datetime(2026, 4, 9, 1, 0)
        sched = {"days": "wed", "start": "22:00", "end": "02:00"}
        assert scheduler.is_schedule_active(sched, now) is True

    def test_midnight_crossing_inactive(self):
        # Thu 03:00 — past end
        now = dt.datetime(2026, 4, 9, 3, 0)
        sched = {"days": "wed", "start": "22:00", "end": "02:00"}
        assert scheduler.is_schedule_active(sched, now) is False

    def test_all_days_any_time(self):
        now = dt.datetime(2026, 4, 11, 15, 0)  # Saturday
        sched = {"days": "all", "start": "00:00", "end": "23:59"}
        assert scheduler.is_schedule_active(sched, now) is True

    def test_empty_schedule_false(self):
        assert scheduler.is_schedule_active({}) is False

    def test_none_schedule_false(self):
        assert scheduler.is_schedule_active(None) is False

    def test_invalid_time_format_false(self):
        now = dt.datetime(2026, 4, 8, 10, 0)
        sched = {"days": "mon-fri", "start": "nope", "end": "17:00"}
        assert scheduler.is_schedule_active(sched, now) is False

    def test_boundary_start_inclusive(self):
        now = dt.datetime(2026, 4, 8, 9, 0)
        sched = {"days": "mon-fri", "start": "09:00", "end": "17:00"}
        assert scheduler.is_schedule_active(sched, now) is True

    def test_boundary_end_exclusive(self):
        now = dt.datetime(2026, 4, 8, 17, 0)
        sched = {"days": "mon-fri", "start": "09:00", "end": "17:00"}
        assert scheduler.is_schedule_active(sched, now) is False
