"""Tests for sentinel.challenges."""
import pytest
import time
from sentinel import challenges, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_challenge(conn):
    cid = challenges.create_challenge(conn, "No YouTube", 24, ["block youtube.com"])
    assert cid > 0


def test_get_challenge(conn):
    cid = challenges.create_challenge(conn, "Test", 1, ["rule1"])
    c = challenges.get_challenge(conn, cid)
    assert c["name"] == "Test"
    assert c["status"] == "active"
    assert "seconds_remaining" in c


def test_get_challenge_nonexistent(conn):
    assert challenges.get_challenge(conn, 9999) is None


def test_challenge_rules_parsed(conn):
    cid = challenges.create_challenge(conn, "Test", 1, ["a", "b", "c"])
    c = challenges.get_challenge(conn, cid)
    assert c["rules"] == ["a", "b", "c"]


def test_get_active_challenges(conn):
    challenges.create_challenge(conn, "C1", 1, [])
    challenges.create_challenge(conn, "C2", 2, [])
    active = challenges.get_active_challenges(conn)
    assert len(active) == 2


def test_complete_before_end_fails(conn):
    cid = challenges.create_challenge(conn, "Long", 24, [])
    assert challenges.complete_challenge(conn, cid) is False  # Not yet expired


def test_complete_after_end(conn):
    cid = challenges.create_challenge(conn, "Short", 1, [])
    # Manipulate end_ts to past
    conn.execute("UPDATE challenges SET end_ts=? WHERE id=?", (time.time() - 10, cid))
    conn.commit()
    assert challenges.complete_challenge(conn, cid) is True


def test_fail_challenge(conn):
    cid = challenges.create_challenge(conn, "Test", 1, [])
    challenges.fail_challenge(conn, cid)
    c = challenges.get_challenge(conn, cid)
    assert c["status"] == "failed"


def test_stats_empty(conn):
    s = challenges.challenge_stats(conn)
    assert s["total"] == 0
    assert s["success_rate"] == 0


def test_stats_with_data(conn):
    cid1 = challenges.create_challenge(conn, "C1", 1, [])
    cid2 = challenges.create_challenge(conn, "C2", 1, [])
    conn.execute("UPDATE challenges SET end_ts=? WHERE id=?", (time.time() - 10, cid1))
    conn.commit()
    challenges.complete_challenge(conn, cid1)
    challenges.fail_challenge(conn, cid2)
    s = challenges.challenge_stats(conn)
    assert s["completed"] == 1
    assert s["failed"] == 1
    assert s["success_rate"] == 50.0


def test_complete_nonexistent(conn):
    assert challenges.complete_challenge(conn, 9999) is False


def test_active_excludes_expired(conn):
    cid = challenges.create_challenge(conn, "Expired", 1, [])
    conn.execute("UPDATE challenges SET end_ts=? WHERE id=?", (time.time() - 100, cid))
    conn.commit()
    active = challenges.get_active_challenges(conn)
    assert len(active) == 0
