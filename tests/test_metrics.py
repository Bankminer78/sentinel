"""Tests for sentinel.metrics."""
import pytest
from sentinel import metrics, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_collect_metrics_empty(conn):
    output = metrics.collect_metrics(conn)
    assert "sentinel_uptime_seconds" in output
    assert "sentinel_rules_total" in output


def test_metrics_has_rules_count(conn):
    db.add_rule(conn, "Rule 1")
    db.add_rule(conn, "Rule 2")
    output = metrics.collect_metrics(conn)
    assert "sentinel_rules_total 2" in output


def test_metrics_prometheus_format(conn):
    output = metrics.collect_metrics(conn)
    assert "# HELP" in output
    assert "# TYPE" in output


def test_uptime():
    up = metrics.get_uptime_seconds()
    assert up >= 0


def test_reset_uptime():
    metrics.reset_uptime()
    assert metrics.get_uptime_seconds() < 2  # Just reset


def test_activities_metric(conn):
    db.log_activity(conn, "App", "Title", "", "test.com", "block")
    output = metrics.collect_metrics(conn)
    assert "sentinel_activities_total 1" in output
    assert "sentinel_blocked_total 1" in output


def test_seen_domains_metric(conn):
    db.save_seen(conn, "a.com", "social")
    db.save_seen(conn, "b.com", "streaming")
    output = metrics.collect_metrics(conn)
    assert "sentinel_seen_domains_total 2" in output


def test_metrics_includes_categories(conn):
    output = metrics.collect_metrics(conn)
    assert "streaming" in output
    assert "social" in output


def test_counter_line():
    line = metrics._counter_line("my_metric", 42, {"label": "test"})
    assert "my_metric" in line
    assert "42" in line
    assert 'label="test"' in line


def test_counter_line_no_labels():
    line = metrics._counter_line("simple", 10)
    assert line == "simple 10"
