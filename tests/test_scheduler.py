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


# ---------------------------------------------------------------------------
# Pomodoro
# ---------------------------------------------------------------------------


class TestPomodoro:
    def test_start_returns_dict(self, conn):
        p = scheduler.start_pomodoro(conn, work_minutes=25, break_minutes=5, cycles=4)
        assert p["state"] == "work"
        assert "id" in p
        assert "ends_at" in p

    def test_get_state_none_when_no_session(self, conn):
        assert scheduler.get_pomodoro_state(conn) is None

    def test_get_state_work_phase(self, conn):
        scheduler.start_pomodoro(conn, work_minutes=25, break_minutes=5, cycles=4)
        s = scheduler.get_pomodoro_state(conn)
        assert s["state"] == "work"
        assert s["cycle"] == 1

    def test_get_state_break_phase(self, conn):
        scheduler.start_pomodoro(conn, work_minutes=25, break_minutes=5, cycles=4)
        # Advance fake time: 26 minutes in -> should be in break of cycle 1
        now = dt.datetime.now() + dt.timedelta(minutes=26)
        s = scheduler.get_pomodoro_state(conn, now=now)
        assert s["state"] == "break"
        assert s["cycle"] == 1

    def test_get_state_second_cycle_work(self, conn):
        scheduler.start_pomodoro(conn, work_minutes=25, break_minutes=5, cycles=4)
        # 31 minutes in -> cycle 2 work
        now = dt.datetime.now() + dt.timedelta(minutes=31)
        s = scheduler.get_pomodoro_state(conn, now=now)
        assert s["state"] == "work"
        assert s["cycle"] == 2

    def test_get_state_done_after_all_cycles(self, conn):
        scheduler.start_pomodoro(conn, work_minutes=25, break_minutes=5, cycles=2)
        # 2 cycles * 30 min = 60 min, advance 65 min
        now = dt.datetime.now() + dt.timedelta(minutes=65)
        s = scheduler.get_pomodoro_state(conn, now=now)
        assert s["state"] == "done"
        assert s["seconds_remaining"] == 0

    def test_done_pomodoro_not_active(self, conn):
        scheduler.start_pomodoro(conn, work_minutes=25, break_minutes=5, cycles=1)
        now = dt.datetime.now() + dt.timedelta(minutes=31)
        scheduler.get_pomodoro_state(conn, now=now)  # triggers state=done
        assert scheduler.get_pomodoro_state(conn) is None

    def test_stop_pomodoro(self, conn):
        scheduler.start_pomodoro(conn)
        scheduler.stop_pomodoro(conn)
        assert scheduler.get_pomodoro_state(conn) is None

    def test_stop_no_session_no_crash(self, conn):
        scheduler.stop_pomodoro(conn)

    def test_seconds_remaining_decreases(self, conn):
        scheduler.start_pomodoro(conn, work_minutes=25, break_minutes=5, cycles=4)
        now1 = dt.datetime.now() + dt.timedelta(minutes=1)
        now2 = dt.datetime.now() + dt.timedelta(minutes=5)
        s1 = scheduler.get_pomodoro_state(conn, now=now1)
        s2 = scheduler.get_pomodoro_state(conn, now=now2)
        assert s1["seconds_remaining"] > s2["seconds_remaining"]


# ---------------------------------------------------------------------------
# Allowances
# ---------------------------------------------------------------------------


class TestAllowances:
    def test_remaining_full_when_unused(self, conn):
        remaining = scheduler.get_allowance_remaining(conn, rule_id=1, daily_limit_seconds=600)
        assert remaining == 600

    def test_record_decreases_remaining(self, conn):
        scheduler.record_allowance_use(conn, rule_id=1, seconds=120)
        remaining = scheduler.get_allowance_remaining(conn, rule_id=1, daily_limit_seconds=600)
        assert remaining == 480

    def test_accumulates_across_calls(self, conn):
        scheduler.record_allowance_use(conn, rule_id=1, seconds=100)
        scheduler.record_allowance_use(conn, rule_id=1, seconds=50)
        scheduler.record_allowance_use(conn, rule_id=1, seconds=25)
        remaining = scheduler.get_allowance_remaining(conn, rule_id=1, daily_limit_seconds=600)
        assert remaining == 425

    def test_remaining_clamps_at_zero(self, conn):
        scheduler.record_allowance_use(conn, rule_id=1, seconds=1000)
        remaining = scheduler.get_allowance_remaining(conn, rule_id=1, daily_limit_seconds=600)
        assert remaining == 0

    def test_rules_isolated(self, conn):
        scheduler.record_allowance_use(conn, rule_id=1, seconds=100)
        scheduler.record_allowance_use(conn, rule_id=2, seconds=200)
        assert scheduler.get_allowance_remaining(conn, 1, 600) == 500
        assert scheduler.get_allowance_remaining(conn, 2, 600) == 400

    def test_resets_at_midnight(self, conn):
        yesterday = dt.datetime.now() - dt.timedelta(days=1)
        scheduler.record_allowance_use(conn, rule_id=1, seconds=500, now=yesterday)
        # Today should be unused
        remaining = scheduler.get_allowance_remaining(conn, rule_id=1, daily_limit_seconds=600)
        assert remaining == 600


# ---------------------------------------------------------------------------
# Focus sessions
# ---------------------------------------------------------------------------


class TestFocusSessions:
    def test_start_returns_dict(self, conn):
        s = scheduler.start_focus_session(conn, duration_minutes=30)
        assert "id" in s
        assert s["locked"] is True
        assert "ends_at" in s

    def test_get_none_when_no_session(self, conn):
        assert scheduler.get_focus_session(conn) is None

    def test_get_active_session(self, conn):
        scheduler.start_focus_session(conn, duration_minutes=30)
        s = scheduler.get_focus_session(conn)
        assert s is not None
        assert s["locked"] is True

    def test_unlocked_session_can_end(self, conn):
        started = scheduler.start_focus_session(conn, duration_minutes=30, locked=False)
        assert scheduler.end_focus_session(conn, started["id"], force=False) is True
        assert scheduler.get_focus_session(conn) is None

    def test_locked_session_cannot_end_early(self, conn):
        started = scheduler.start_focus_session(conn, duration_minutes=30, locked=True)
        assert scheduler.end_focus_session(conn, started["id"], force=False) is False
        assert scheduler.get_focus_session(conn) is not None

    def test_locked_session_force_end(self, conn):
        started = scheduler.start_focus_session(conn, duration_minutes=30, locked=True)
        assert scheduler.end_focus_session(conn, started["id"], force=True) is True
        assert scheduler.get_focus_session(conn) is None

    def test_expired_session_auto_cleared(self, conn):
        scheduler.start_focus_session(conn, duration_minutes=1)
        future = dt.datetime.now() + dt.timedelta(minutes=5)
        s = scheduler.get_focus_session(conn, now=future)
        assert s is None

    def test_end_nonexistent_returns_false(self, conn):
        assert scheduler.end_focus_session(conn, 9999) is False

    def test_seconds_remaining_present(self, conn):
        scheduler.start_focus_session(conn, duration_minutes=30)
        s = scheduler.get_focus_session(conn)
        assert s["seconds_remaining"] > 0
        assert s["seconds_remaining"] <= 30 * 60

    def test_only_one_active_returned(self, conn):
        # Start two — get_active_focus returns most recent
        scheduler.start_focus_session(conn, duration_minutes=30)
        second = scheduler.start_focus_session(conn, duration_minutes=45)
        s = scheduler.get_focus_session(conn)
        assert s["id"] == second["id"]
