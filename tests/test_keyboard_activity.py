"""Tests for sentinel.keyboard_activity."""
import pytest
import time
from unittest.mock import patch, MagicMock
from sentinel import keyboard_activity as ka, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_log_activity(conn):
    ka.log_activity(conn, 100, 20, "Chrome")
    summary = ka.get_activity_summary(conn, minutes=60)
    assert summary["keys"] == 100
    assert summary["mouse"] == 20


def test_log_multiple(conn):
    ka.log_activity(conn, 50, 10)
    ka.log_activity(conn, 30, 5)
    summary = ka.get_activity_summary(conn, minutes=60)
    assert summary["keys"] == 80


def test_typing_rate(conn):
    ka.log_activity(conn, 100, 0)
    rate = ka.get_typing_rate(conn, minutes=10)
    assert rate == 10.0


def test_typing_rate_empty(conn):
    assert ka.get_typing_rate(conn, minutes=10) == 0.0


def test_context_switches(conn):
    ka.log_activity(conn, 10, 0, "Chrome")
    ka.log_activity(conn, 10, 0, "Safari")
    ka.log_activity(conn, 10, 0, "Chrome")
    switches = ka.detect_context_switches(conn, window_seconds=600)
    assert switches == 2  # Chrome and Safari


def test_context_switches_empty(conn):
    assert ka.detect_context_switches(conn) == 0


def test_get_idle_time_mock():
    mock_output = """    | | |   +-o IOHIDSystem  <class IOHIDSystem>
    | | |     |   "HIDIdleTime" = 5000000000
    """
    mock_result = MagicMock(returncode=0, stdout=mock_output)
    with patch("sentinel.keyboard_activity.subprocess.run", return_value=mock_result):
        idle = ka.get_idle_time_seconds()
        assert idle == 5.0


def test_get_idle_time_error():
    with patch("sentinel.keyboard_activity.subprocess.run", side_effect=Exception("fail")):
        assert ka.get_idle_time_seconds() == 0.0


def test_is_idle_false():
    with patch("sentinel.keyboard_activity.get_idle_time_seconds", return_value=10.0):
        assert ka.is_idle(threshold_seconds=60) is False


def test_is_idle_true():
    with patch("sentinel.keyboard_activity.get_idle_time_seconds", return_value=120.0):
        assert ka.is_idle(threshold_seconds=60) is True


def test_activity_outside_window(conn):
    # Insert old activity
    conn.execute("""CREATE TABLE IF NOT EXISTS keyboard_log (
        id INTEGER PRIMARY KEY, ts REAL, key_count INTEGER,
        mouse_count INTEGER, window TEXT)""")
    conn.execute(
        "INSERT INTO keyboard_log (ts, key_count, mouse_count, window) VALUES (?,?,?,?)",
        (time.time() - 7200, 100, 0, ""))
    conn.commit()
    rate = ka.get_typing_rate(conn, minutes=10)
    assert rate == 0.0  # Outside window


def test_get_activity_summary_minutes(conn):
    ka.log_activity(conn, 50, 10)
    summary = ka.get_activity_summary(conn, minutes=30)
    assert summary["minutes"] == 30
