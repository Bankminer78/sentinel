"""Tests for sentinel.blocklist_marketplace."""
import pytest
from unittest.mock import patch
from sentinel import blocklist_marketplace as bm, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_list_available():
    available = bm.list_available()
    assert len(available) > 0
    assert all("id" in b and "name" in b for b in available)


def test_get_blocklist():
    bl = bm.get_blocklist("streaming_mega")
    assert bl is not None
    assert "domains" in bl


def test_get_nonexistent():
    assert bm.get_blocklist("ghost") is None


def test_subscribe(conn):
    with patch("sentinel.blocker._sync_hosts"):
        count = bm.subscribe(conn, "streaming_mega")
        assert count > 0


def test_subscribe_invalid(conn):
    assert bm.subscribe(conn, "invalid") == 0


def test_unsubscribe(conn):
    with patch("sentinel.blocker._sync_hosts"):
        bm.subscribe(conn, "social_detox")
        bm.unsubscribe(conn, "social_detox")
        assert bm.is_subscribed(conn, "social_detox") is False


def test_is_subscribed(conn):
    with patch("sentinel.blocker._sync_hosts"):
        bm.subscribe(conn, "streaming_mega")
        assert bm.is_subscribed(conn, "streaming_mega") is True


def test_get_subscriptions_empty(conn):
    assert bm.get_subscriptions(conn) == []


def test_get_subscriptions(conn):
    with patch("sentinel.blocker._sync_hosts"):
        bm.subscribe(conn, "streaming_mega")
    subs = bm.get_subscriptions(conn)
    assert len(subs) == 1


def test_count_available():
    assert bm.count_available() >= 5


def test_search_blocklists():
    results = bm.search_blocklists("social")
    assert len(results) >= 1


def test_search_no_match():
    results = bm.search_blocklists("xyznomatch")
    assert results == []
