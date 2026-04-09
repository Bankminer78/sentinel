"""Tests for sentinel.custom_metrics."""
import pytest
from sentinel import custom_metrics as cm, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_metric(conn):
    mid = cm.create_metric(conn, "pushups", "reps", "Daily pushup count", 100)
    assert mid > 0


def test_get_metrics(conn):
    cm.create_metric(conn, "steps", "count")
    cm.create_metric(conn, "water", "oz")
    metrics = cm.get_metrics(conn)
    assert len(metrics) == 2


def test_get_metric(conn):
    mid = cm.create_metric(conn, "test", "units")
    m = cm.get_metric(conn, mid)
    assert m["name"] == "test"


def test_get_nonexistent(conn):
    assert cm.get_metric(conn, 999) is None


def test_delete_metric(conn):
    mid = cm.create_metric(conn, "temp", "")
    cm.delete_metric(conn, mid)
    assert cm.get_metric(conn, mid) is None


def test_log_value(conn):
    mid = cm.create_metric(conn, "pushups", "reps")
    lid = cm.log_value(conn, mid, 50)
    assert lid > 0


def test_get_values(conn):
    mid = cm.create_metric(conn, "test", "")
    cm.log_value(conn, mid, 10)
    cm.log_value(conn, mid, 20)
    values = cm.get_values(conn, mid)
    assert len(values) == 2


def test_metric_stats(conn):
    mid = cm.create_metric(conn, "test", "")
    for v in [10, 20, 30]:
        cm.log_value(conn, mid, v)
    stats = cm.metric_stats(conn, mid)
    assert stats["count"] == 3
    assert stats["avg"] == 20.0
    assert stats["min"] == 10
    assert stats["max"] == 30


def test_metric_stats_empty(conn):
    mid = cm.create_metric(conn, "empty", "")
    stats = cm.metric_stats(conn, mid)
    assert stats["count"] == 0


def test_metric_trend_stable(conn):
    mid = cm.create_metric(conn, "test", "")
    trend = cm.metric_trend(conn, mid)
    assert trend == "stable"


def test_all_metrics_today(conn):
    cm.create_metric(conn, "a", "")
    cm.create_metric(conn, "b", "")
    today = cm.all_metrics_today(conn)
    assert len(today) == 2
