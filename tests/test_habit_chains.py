"""Tests for sentinel.habit_chains."""
import pytest
from sentinel import habit_chains as hc, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_chain(conn):
    cid = hc.create_chain(conn, "Morning", [1, 2, 3], "Morning routine", "wake_up")
    assert cid > 0


def test_get_chain(conn):
    cid = hc.create_chain(conn, "Test", [1, 2])
    c = hc.get_chain(conn, cid)
    assert c["name"] == "Test"
    assert c["habit_ids"] == [1, 2]


def test_list_chains(conn):
    hc.create_chain(conn, "C1", [1])
    hc.create_chain(conn, "C2", [2])
    assert len(hc.list_chains(conn)) == 2


def test_delete_chain(conn):
    cid = hc.create_chain(conn, "Delete", [1])
    hc.delete_chain(conn, cid)
    assert hc.total_chains(conn) == 0


def test_log_completion(conn):
    cid = hc.create_chain(conn, "Test", [1, 2, 3])
    lid = hc.log_completion(conn, cid, 3)
    assert lid > 0


def test_completion_rate_empty(conn):
    cid = hc.create_chain(conn, "Test", [1, 2, 3])
    assert hc.completion_rate(conn, cid) == 0


def test_completion_rate(conn):
    cid = hc.create_chain(conn, "Test", [1, 2, 3, 4])
    hc.log_completion(conn, cid, 2)  # 2/4 = 50%
    assert hc.completion_rate(conn, cid) == 50.0


def test_streak_empty(conn):
    cid = hc.create_chain(conn, "Test", [1])
    assert hc.streak(conn, cid) == 0


def test_streak(conn):
    cid = hc.create_chain(conn, "Test", [1])
    hc.log_completion(conn, cid, 1)  # all 1 completed
    assert hc.streak(conn, cid) >= 1


def test_chains_by_trigger(conn):
    hc.create_chain(conn, "C1", [1], trigger="morning")
    hc.create_chain(conn, "C2", [2], trigger="evening")
    assert len(hc.chains_by_trigger(conn, "morning")) == 1


def test_total_chains(conn):
    hc.create_chain(conn, "C1", [1])
    hc.create_chain(conn, "C2", [2])
    assert hc.total_chains(conn) == 2
