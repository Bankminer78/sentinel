"""Tests for sentinel.group_challenges."""
import pytest
from sentinel import group_challenges as gc, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_challenge(conn):
    cid = gc.create_group_challenge(conn, "No YouTube week", "Block YouTube for a week", 7, "alice")
    assert cid > 0


def test_join_challenge(conn):
    cid = gc.create_group_challenge(conn, "Test", "desc", 7)
    gc.join_challenge(conn, cid, "alice")
    challenge = gc.get_challenge(conn, cid)
    assert len(challenge["members"]) == 1


def test_multiple_members(conn):
    cid = gc.create_group_challenge(conn, "Test", "desc", 7)
    for name in ["alice", "bob", "carol"]:
        gc.join_challenge(conn, cid, name)
    challenge = gc.get_challenge(conn, cid)
    assert len(challenge["members"]) == 3


def test_leave_challenge(conn):
    cid = gc.create_group_challenge(conn, "Test", "desc", 7)
    gc.join_challenge(conn, cid, "alice")
    gc.leave_challenge(conn, cid, "alice")
    challenge = gc.get_challenge(conn, cid)
    assert len(challenge["members"]) == 0


def test_update_score(conn):
    cid = gc.create_group_challenge(conn, "Test", "desc", 7)
    gc.join_challenge(conn, cid, "alice")
    gc.update_member_score(conn, cid, "alice", 85.0)
    challenge = gc.get_challenge(conn, cid)
    assert challenge["members"][0]["score"] == 85.0


def test_get_nonexistent(conn):
    assert gc.get_challenge(conn, 999) is None


def test_list_active(conn):
    gc.create_group_challenge(conn, "C1", "", 7)
    gc.create_group_challenge(conn, "C2", "", 7)
    active = gc.list_challenges(conn, "active")
    assert len(active) == 2


def test_leaderboard(conn):
    cid = gc.create_group_challenge(conn, "Test", "desc", 7)
    gc.join_challenge(conn, cid, "bob")
    gc.join_challenge(conn, cid, "alice")
    gc.update_member_score(conn, cid, "bob", 70)
    gc.update_member_score(conn, cid, "alice", 90)
    lb = gc.get_leaderboard(conn, cid)
    assert lb[0]["member"] == "alice"
    assert lb[1]["member"] == "bob"


def test_finalize(conn):
    cid = gc.create_group_challenge(conn, "Test", "desc", 7)
    gc.join_challenge(conn, cid, "alice")
    gc.update_member_score(conn, cid, "alice", 100)
    result = gc.finalize(conn, cid)
    assert result["winner"]["member"] == "alice"


def test_delete_challenge(conn):
    cid = gc.create_group_challenge(conn, "Test", "desc", 7)
    gc.join_challenge(conn, cid, "alice")
    gc.delete_challenge(conn, cid)
    assert gc.get_challenge(conn, cid) is None


def test_seconds_remaining(conn):
    cid = gc.create_group_challenge(conn, "Test", "desc", 7)
    challenge = gc.get_challenge(conn, cid)
    assert challenge["seconds_remaining"] > 0


def test_join_idempotent(conn):
    cid = gc.create_group_challenge(conn, "Test", "desc", 7)
    gc.join_challenge(conn, cid, "alice")
    gc.join_challenge(conn, cid, "alice")
    challenge = gc.get_challenge(conn, cid)
    assert len(challenge["members"]) == 1
