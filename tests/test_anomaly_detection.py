"""Tests for sentinel.anomaly_detection."""
import pytest
from sentinel import anomaly_detection as ad, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_mean_std_empty():
    mean, std = ad._mean_std([])
    assert mean == 0
    assert std == 0


def test_mean_std_basic():
    mean, std = ad._mean_std([1, 2, 3, 4, 5])
    assert mean == 3.0
    assert std > 0


def test_is_anomaly_true():
    # Value way above mean
    assert ad.is_anomaly(100, 5, 2) is True


def test_is_anomaly_false():
    assert ad.is_anomaly(5, 5, 2) is False


def test_is_anomaly_zero_std():
    assert ad.is_anomaly(5, 5, 0) is False


def test_detect_spending_empty(conn):
    assert ad.detect_spending_anomalies(conn) == []


def test_detect_activity_empty(conn):
    assert ad.detect_activity_anomalies(conn) == []


def test_detect_mood_empty(conn):
    assert ad.detect_mood_anomalies(conn) == []


def test_detect_all_empty(conn):
    result = ad.detect_all_anomalies(conn)
    assert "spending" in result
    assert "activity" in result
    assert "mood" in result


def test_z_score():
    assert ad.z_score(10, 5, 2) == 2.5
    assert ad.z_score(5, 5, 0) == 0


def test_recent_unusual_days_empty(conn):
    assert ad.recent_unusual_days(conn) == []
