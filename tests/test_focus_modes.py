"""Tests for sentinel.focus_modes — advanced focus patterns."""

import pytest

from sentinel import focus_modes, scheduler


class TestListModes:
    def test_returns_list(self):
        modes = focus_modes.list_modes()
        assert isinstance(modes, list)
        assert len(modes) >= 6

    def test_contains_pomodoro(self):
        names = {m["name"] for m in focus_modes.list_modes()}
        assert "pomodoro" in names

    def test_contains_all_expected(self):
        names = {m["name"] for m in focus_modes.list_modes()}
        for n in ("pomodoro", "52_17", "flowmodoro", "ultradian", "animedoro", "deep_work"):
            assert n in names

    def test_each_has_work_and_break(self):
        for m in focus_modes.list_modes():
            assert "work" in m
            assert "break" in m
            assert "cycles" in m


class TestGetMode:
    def test_get_pomodoro(self):
        m = focus_modes.get_mode("pomodoro")
        assert m["work"] == 25
        assert m["break"] == 5

    def test_get_deep_work(self):
        m = focus_modes.get_mode("deep_work")
        assert m["work"] == 120

    def test_get_52_17(self):
        m = focus_modes.get_mode("52_17")
        assert m["work"] == 52
        assert m["break"] == 17

    def test_unknown_raises(self):
        with pytest.raises(ValueError):
            focus_modes.get_mode("bogus")

    def test_returns_copy(self):
        m = focus_modes.get_mode("pomodoro")
        m["work"] = 999
        assert focus_modes.get_mode("pomodoro")["work"] == 25


class TestStartMode:
    def test_start_pomodoro(self, conn):
        state = focus_modes.start_mode(conn, "pomodoro")
        assert state["mode"] == "pomodoro"
        assert state["state"] == "work"
        assert "id" in state

    def test_start_deep_work_uses_long_work(self, conn):
        state = focus_modes.start_mode(conn, "deep_work")
        p = scheduler.get_pomodoro_state(conn)
        assert p is not None
        assert state["mode"] == "deep_work"

    def test_start_unknown_raises(self, conn):
        with pytest.raises(ValueError):
            focus_modes.start_mode(conn, "nope")


class TestCurrentModeState:
    def test_no_session(self, conn):
        assert focus_modes.current_mode_state(conn) == {}

    def test_with_session(self, conn):
        focus_modes.start_mode(conn, "pomodoro")
        state = focus_modes.current_mode_state(conn)
        assert state
        assert state["state"] == "work"


class TestStopCurrentMode:
    def test_stop_clears(self, conn):
        focus_modes.start_mode(conn, "pomodoro")
        focus_modes.stop_current_mode(conn)
        assert focus_modes.current_mode_state(conn) == {}
