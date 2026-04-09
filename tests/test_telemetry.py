"""Tests for sentinel.telemetry."""
import pytest
from sentinel import telemetry, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_disabled_by_default(conn):
    assert telemetry.is_enabled(conn) is False


def test_enable(conn):
    telemetry.enable(conn)
    assert telemetry.is_enabled(conn) is True


def test_disable(conn):
    telemetry.enable(conn)
    telemetry.disable(conn)
    assert telemetry.is_enabled(conn) is False


def test_track_disabled(conn):
    telemetry.track(conn, "test_event", {"a": 1})
    events = telemetry.get_events(conn)
    # Not enabled, so no event
    assert events == []


def test_track_enabled(conn):
    telemetry.enable(conn)
    telemetry.track(conn, "test_event", {"a": 1})
    events = telemetry.get_events(conn)
    assert len(events) == 1
    assert events[0]["event"] == "test_event"


def test_track_multiple(conn):
    telemetry.enable(conn)
    telemetry.track(conn, "event1")
    telemetry.track(conn, "event2")
    telemetry.track(conn, "event1")
    events = telemetry.get_events(conn)
    assert len(events) == 3


def test_event_counts(conn):
    telemetry.enable(conn)
    telemetry.track(conn, "event1")
    telemetry.track(conn, "event1")
    telemetry.track(conn, "event2")
    counts = telemetry.event_counts(conn)
    assert counts["event1"] == 2
    assert counts["event2"] == 1


def test_purge_old(conn):
    telemetry.enable(conn)
    telemetry.track(conn, "test")
    # Manually set old timestamp
    import time
    conn.execute("UPDATE telemetry_events SET ts=?", (time.time() - 100 * 86400,))
    conn.commit()
    count = telemetry.purge_old(conn, days=30)
    assert count >= 1


def test_summary(conn):
    telemetry.enable(conn)
    telemetry.track(conn, "e1")
    summary = telemetry.summary(conn)
    assert summary["enabled"] is True
    assert summary["total_events"] == 1


def test_summary_disabled(conn):
    summary = telemetry.summary(conn)
    assert summary["enabled"] is False
