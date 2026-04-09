"""Tests for sentinel.journeys."""
from sentinel import journeys


def test_create_journey(conn):
    jid = journeys.create_journey(conn, "Learn Rust", "become rustacean", ["read book", "build app"])
    assert jid > 0


def test_get_journeys_active(conn):
    journeys.create_journey(conn, "a", "d", ["m1"])
    assert len(journeys.get_journeys(conn)) == 1


def test_get_journeys_empty(conn):
    assert journeys.get_journeys(conn) == []


def test_complete_milestone(conn):
    jid = journeys.create_journey(conn, "j", "d", ["m1", "m2", "m3"])
    journeys.complete_milestone(conn, jid, 0)
    p = journeys.get_journey_progress(conn, jid)
    assert p["completed"] == 1
    assert p["total"] == 3


def test_progress_percent(conn):
    jid = journeys.create_journey(conn, "j", "d", ["m1", "m2", "m3", "m4"])
    journeys.complete_milestone(conn, jid, 0)
    journeys.complete_milestone(conn, jid, 1)
    p = journeys.get_journey_progress(conn, jid)
    assert p["percent"] == 50.0


def test_complete_all_milestones(conn):
    jid = journeys.create_journey(conn, "j", "d", ["m1", "m2"])
    journeys.complete_milestone(conn, jid, 0)
    journeys.complete_milestone(conn, jid, 1)
    p = journeys.get_journey_progress(conn, jid)
    assert p["is_complete"] is True
    assert p["percent"] == 100.0


def test_completed_journey_not_active(conn):
    jid = journeys.create_journey(conn, "j", "d", ["m1"])
    journeys.complete_milestone(conn, jid, 0)
    assert journeys.get_journeys(conn, active=True) == []
    assert len(journeys.get_journeys(conn, active=False)) == 1


def test_complete_milestone_invalid_index(conn):
    jid = journeys.create_journey(conn, "j", "d", ["m1"])
    journeys.complete_milestone(conn, jid, 5)
    p = journeys.get_journey_progress(conn, jid)
    assert p["completed"] == 0


def test_complete_milestone_negative(conn):
    jid = journeys.create_journey(conn, "j", "d", ["m1"])
    journeys.complete_milestone(conn, jid, -1)
    p = journeys.get_journey_progress(conn, jid)
    assert p["completed"] == 0


def test_complete_milestone_nonexistent(conn):
    journeys.complete_milestone(conn, 999, 0)  # no crash


def test_delete_journey(conn):
    jid = journeys.create_journey(conn, "j", "d", ["m1"])
    journeys.delete_journey(conn, jid)
    assert journeys.get_journeys(conn) == []


def test_progress_nonexistent(conn):
    assert journeys.get_journey_progress(conn, 999) is None


def test_milestones_deduplicated(conn):
    jid = journeys.create_journey(conn, "j", "d", ["m1", "m2"])
    journeys.complete_milestone(conn, jid, 0)
    journeys.complete_milestone(conn, jid, 0)
    p = journeys.get_journey_progress(conn, jid)
    assert p["completed"] == 1


def test_progress_empty_milestones(conn):
    jid = journeys.create_journey(conn, "j", "d", [])
    p = journeys.get_journey_progress(conn, jid)
    assert p["percent"] == 0.0
    assert p["total"] == 0
