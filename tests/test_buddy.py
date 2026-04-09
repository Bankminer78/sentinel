"""Tests for sentinel.buddy."""
import pytest
from sentinel import buddy, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_buddy(conn):
    bid = buddy.add_buddy(conn, "Alice", "alice@example.com")
    assert bid > 0


def test_get_buddies(conn):
    buddy.add_buddy(conn, "Alice", "a@ex.com")
    buddy.add_buddy(conn, "Bob", "b@ex.com")
    assert len(buddy.get_buddies(conn)) == 2


def test_remove_buddy(conn):
    bid = buddy.add_buddy(conn, "Test", "t@ex.com")
    buddy.remove_buddy(conn, bid)
    assert len(buddy.get_buddies(conn)) == 0
    assert len(buddy.get_buddies(conn, active_only=False)) == 1


def test_log_message(conn):
    bid = buddy.add_buddy(conn, "Alice", "a@ex.com")
    mid = buddy.log_message(conn, bid, "out", "Hello")
    assert mid > 0


def test_get_messages(conn):
    bid = buddy.add_buddy(conn, "Alice", "a@ex.com")
    buddy.log_message(conn, bid, "out", "Hi")
    buddy.log_message(conn, bid, "in", "Hello back")
    assert len(buddy.get_messages(conn, bid)) == 2


def test_last_check_in_none(conn):
    bid = buddy.add_buddy(conn, "Alice", "a@ex.com")
    assert buddy.last_check_in(conn, bid) == 0


def test_last_check_in(conn):
    bid = buddy.add_buddy(conn, "Alice", "a@ex.com")
    buddy.log_message(conn, bid, "out", "Hello")
    assert buddy.last_check_in(conn, bid) > 0


def test_check_in(conn):
    bid = buddy.add_buddy(conn, "Alice", "a@ex.com")
    mid = buddy.check_in(conn, bid, "Good morning")
    assert mid > 0


def test_receive_from_buddy(conn):
    bid = buddy.add_buddy(conn, "Alice", "a@ex.com")
    mid = buddy.receive_from_buddy(conn, bid, "Hey!")
    assert mid > 0


def test_buddies_needing_check_in(conn):
    bid = buddy.add_buddy(conn, "Alice", "a@ex.com")
    # No check-ins, so overdue
    needing = buddy.buddies_needing_check_in(conn)
    assert len(needing) >= 1


def test_total_buddies(conn):
    buddy.add_buddy(conn, "A", "a")
    buddy.add_buddy(conn, "B", "b")
    assert buddy.total_buddies(conn) == 2
