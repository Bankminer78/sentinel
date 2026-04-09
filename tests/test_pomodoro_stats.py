"""Tests for sentinel.pomodoro_stats."""
import pytest
import time
from sentinel import pomodoro_stats as ps, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_pomodoros_completed_empty(conn):
    assert ps.pomodoros_completed(conn) == 0


def test_pomodoros_completed(conn):
    ps._ensure_table(conn)
    conn.execute(
        "INSERT INTO pomodoro_sessions (start_ts, work_minutes, total_cycles, state) VALUES (?, 25, 4, 'done')",
        (time.time(),))
    conn.commit()
    assert ps.pomodoros_completed(conn) == 1


def test_total_focus_minutes_empty(conn):
    assert ps.total_focus_minutes(conn) == 0


def test_total_focus_minutes(conn):
    ps._ensure_table(conn)
    conn.execute(
        "INSERT INTO pomodoro_sessions (start_ts, work_minutes, current_cycle) VALUES (?, 25, 4)",
        (time.time(),))
    conn.commit()
    assert ps.total_focus_minutes(conn) == 100  # 25 * 4


def test_avg_session_length_empty(conn):
    assert ps.avg_session_length(conn) == 0


def test_pomodoros_per_day_empty(conn):
    assert ps.pomodoros_per_day(conn) == {}


def test_pomodoros_per_day(conn):
    ps._ensure_table(conn)
    conn.execute(
        "INSERT INTO pomodoro_sessions (start_ts, work_minutes) VALUES (?, 25)",
        (time.time(),))
    conn.commit()
    per_day = ps.pomodoros_per_day(conn)
    assert len(per_day) >= 1


def test_best_day_empty(conn):
    assert ps.best_day(conn) is None


def test_pomodoro_streak_empty(conn):
    assert ps.pomodoro_streak(conn) == 0


def test_peak_hours_empty(conn):
    assert ps.peak_hours(conn) == []


def test_completion_rate_empty(conn):
    assert ps.completion_rate(conn) == 0


def test_weekly_focus_hours(conn):
    assert ps.weekly_focus_hours(conn) == 0


def test_summary(conn):
    summary = ps.pomodoro_summary(conn)
    assert "completed_this_week" in summary
    assert "focus_hours_week" in summary
