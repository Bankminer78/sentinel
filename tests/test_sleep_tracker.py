"""Tests for sentinel.sleep_tracker."""
import pytest
import time
from datetime import datetime
from sentinel import sleep_tracker as st, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_log_sleep(conn):
    wake = time.time()
    bed = wake - 8 * 3600
    sid = st.log_sleep(conn, bed, wake, quality=8)
    assert sid > 0


def test_get_sleep(conn):
    wake = time.time()
    bed = wake - 7 * 3600
    st.log_sleep(conn, bed, wake, quality=7)
    today = datetime.now().strftime("%Y-%m-%d")
    sleep = st.get_sleep(conn, today)
    assert sleep["quality"] == 7


def test_get_sleep_none(conn):
    assert st.get_sleep(conn, "1999-01-01") is None


def test_get_last_n_days(conn):
    for i in range(3):
        wake = time.time() - i * 86400
        st.log_sleep(conn, wake - 8 * 3600, wake)
    assert len(st.get_last_n_days(conn, n=3)) == 3


def test_avg_duration(conn):
    wake = time.time()
    st.log_sleep(conn, wake - 8 * 3600, wake)
    assert st.avg_sleep_duration(conn) == 8.0


def test_avg_quality(conn):
    wake = time.time()
    st.log_sleep(conn, wake - 7 * 3600, wake, quality=9)
    assert st.avg_sleep_quality(conn) == 9.0


def test_sleep_debt(conn):
    wake = time.time()
    st.log_sleep(conn, wake - 6 * 3600, wake)  # 6h vs 8h target
    debt = st.sleep_debt(conn)
    assert debt == 2.0


def test_nights_with_target(conn):
    wake = time.time()
    st.log_sleep(conn, wake - 8 * 3600, wake)
    assert st.nights_with_target(conn, target_hours=7) == 1


def test_bedtime_consistency(conn):
    for i in range(5):
        wake = time.time() - i * 86400
        st.log_sleep(conn, wake - 8 * 3600, wake)
    consistency = st.bedtime_consistency(conn)
    assert consistency >= 0


def test_delete_sleep(conn):
    wake = time.time()
    st.log_sleep(conn, wake - 8 * 3600, wake)
    today = datetime.now().strftime("%Y-%m-%d")
    st.delete_sleep(conn, today)
    assert st.get_sleep(conn, today) is None
