"""Tests for sentinel.screen_time."""
import pytest
import time
from datetime import datetime
from sentinel import screen_time as st, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_total_today_empty(conn):
    assert st.total_today(conn) == 0


def test_total_today(conn):
    today_start = datetime.combine(datetime.now().date(), datetime.min.time()).timestamp()
    conn.execute(
        "INSERT INTO activity_log (ts, app, title, duration_s) VALUES (?, 'App', 'T', 3600)",
        (today_start + 100,))
    conn.commit()
    # 3600 seconds = 1 hour
    assert st.total_today(conn) == 1.0


def test_total_for_days(conn):
    now = time.time()
    conn.execute(
        "INSERT INTO activity_log (ts, app, title, duration_s) VALUES (?, 'App', 'T', 1800)",
        (now,))
    conn.commit()
    assert st.total_for_days(conn, days=7) == 0.5


def test_by_app_today_empty(conn):
    assert st.by_app_today(conn) == {}


def test_by_app_today(conn):
    today_start = datetime.combine(datetime.now().date(), datetime.min.time()).timestamp()
    conn.execute(
        "INSERT INTO activity_log (ts, app, title, duration_s) VALUES (?, 'Chrome', 'T', 600)",
        (today_start + 100,))
    conn.commit()
    result = st.by_app_today(conn)
    assert result["Chrome"] == 10.0  # minutes


def test_top_apps_today(conn):
    today_start = datetime.combine(datetime.now().date(), datetime.min.time()).timestamp()
    conn.execute(
        "INSERT INTO activity_log (ts, app, title, duration_s) VALUES (?, 'A', '', 300)",
        (today_start + 10,))
    conn.execute(
        "INSERT INTO activity_log (ts, app, title, duration_s) VALUES (?, 'B', '', 600)",
        (today_start + 20,))
    conn.commit()
    top = st.top_apps_today(conn)
    assert top[0]["app"] == "B"


def test_hourly_usage(conn):
    usage = st.hourly_usage(conn)
    assert len(usage) == 24


def test_weekly_average(conn):
    assert st.weekly_average_hours(conn) == 0


def test_compare_to_yesterday(conn):
    result = st.compare_to_yesterday(conn)
    assert "today" in result
    assert "yesterday" in result
    assert "diff" in result


def test_target_tracker(conn):
    result = st.target_tracker(conn, 8.0)
    assert result["target"] == 8.0
    assert result["exceeded"] is False


def test_longest_session(conn):
    assert st.longest_session_today(conn) == 0
