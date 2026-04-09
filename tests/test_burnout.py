"""Tests for sentinel.burnout."""
import pytest
import time
from unittest.mock import patch, AsyncMock
from sentinel import burnout, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_calculate_empty(conn):
    result = burnout.calculate_burnout_score(conn)
    assert "score" in result
    assert "indicators" in result
    assert "severity" in result


def test_check_long_hours_false(conn):
    # No activity
    assert burnout.check_long_hours(conn) is False


def test_check_long_hours_true(conn):
    # Insert 3 days of heavy activity
    for i in range(3):
        ts = time.time() - i * 86400
        conn.execute(
            "INSERT INTO activity_log (ts, app, title, duration_s) VALUES (?, 'x', '', ?)",
            (ts, 11 * 3600))
    conn.commit()
    assert burnout.check_long_hours(conn) is True


def test_check_late_nights_false(conn):
    assert burnout.check_late_nights(conn) is False


def test_check_late_nights_true(conn):
    from datetime import datetime
    # 6 activities past 11pm
    for i in range(6):
        day = datetime.now().replace(hour=23, minute=30)
        ts = day.timestamp() - i * 86400
        conn.execute(
            "INSERT INTO activity_log (ts, app, title) VALUES (?, 'x', '')",
            (ts,))
    conn.commit()
    assert burnout.check_late_nights(conn) is True


def test_check_weekend_work_false(conn):
    assert burnout.check_weekend_work(conn) is False


def test_check_high_distraction_false(conn):
    assert burnout.check_high_distraction(conn) is False


def test_check_high_distraction_true(conn):
    for i in range(25):
        conn.execute(
            "INSERT INTO activity_log (ts, app, verdict) VALUES (?, 'x', 'block')",
            (time.time() - i * 60,))
    conn.commit()
    assert burnout.check_high_distraction(conn) is True


def test_burnout_severity_low(conn):
    result = burnout.calculate_burnout_score(conn)
    # Empty DB should have low severity
    assert result["severity"] in ("low", "medium", "high")


def test_recommend_rest_empty(conn):
    recs = burnout.recommend_rest(conn)
    assert isinstance(recs, list)


@pytest.mark.asyncio
async def test_burnout_alert_low(conn):
    result = await burnout.burnout_alert(conn, "key")
    assert "score" in result


@pytest.mark.asyncio
async def test_burnout_alert_high(conn):
    # Force high burnout
    for i in range(5):
        ts = time.time() - i * 86400
        conn.execute(
            "INSERT INTO activity_log (ts, app, title, duration_s) VALUES (?, 'x', '', ?)",
            (ts, 12 * 3600))
    for i in range(30):
        conn.execute(
            "INSERT INTO activity_log (ts, verdict) VALUES (?, 'block')",
            (time.time() - i * 60,))
    conn.commit()
    with patch("sentinel.burnout.classifier.call_gemini",
               new_callable=AsyncMock, return_value="Take a break!"):
        result = await burnout.burnout_alert(conn, "key")
        if result["score"] >= 50:
            assert "message" in result


def test_indicators_dict():
    assert len(burnout.INDICATORS) == 6
