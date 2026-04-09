"""Tests for sentinel.steps."""
import pytest
from sentinel import steps as st, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_log_steps(conn):
    result = st.log_steps(conn, 8000)
    assert result == 8000


def test_get_steps(conn):
    st.log_steps(conn, 5000)
    today = st.get_steps(conn)
    assert today["steps"] == 5000
    assert today["distance_km"] > 0


def test_get_steps_nonexistent(conn):
    result = st.get_steps(conn, "1999-01-01")
    assert result["steps"] == 0


def test_total_steps(conn):
    st.log_steps(conn, 10000)
    assert st.total_steps(conn, days=7) == 10000


def test_avg_daily_steps(conn):
    st.log_steps(conn, 7000)
    avg = st.avg_daily_steps(conn, days=7)
    assert avg == 1000  # 7000 / 7


def test_days_target_reached(conn):
    st.log_steps(conn, 12000)
    assert st.days_target_reached(conn) == 1


def test_streak_empty(conn):
    assert st.streak(conn) == 0


def test_streak(conn):
    st.log_steps(conn, 10000)
    assert st.streak(conn) >= 1


def test_progress_today(conn):
    st.log_steps(conn, 5000)
    prog = st.progress_today(conn)
    assert prog["steps"] == 5000
    assert prog["percent"] == 50.0


def test_delete_log(conn):
    st.log_steps(conn, 5000)
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    st.delete_log(conn, today)
    assert st.get_steps(conn)["steps"] == 0


def test_weekly_total(conn):
    st.log_steps(conn, 10000)
    assert st.weekly_total(conn) == 10000


def test_monthly_total(conn):
    st.log_steps(conn, 10000)
    assert st.monthly_total(conn) == 10000
