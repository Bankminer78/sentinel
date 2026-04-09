"""Tests for sentinel.social_feed."""
import pytest
from sentinel import social_feed, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_post(conn):
    pid = social_feed.create_post(conn, "alice", "Shipped the MVP!")
    assert pid > 0


def test_get_feed(conn):
    social_feed.create_post(conn, "alice", "Post 1")
    social_feed.create_post(conn, "bob", "Post 2")
    feed = social_feed.get_feed(conn)
    assert len(feed) == 2


def test_empty_feed(conn):
    assert social_feed.get_feed(conn) == []


def test_get_post(conn):
    pid = social_feed.create_post(conn, "alice", "Hello")
    p = social_feed.get_post(conn, pid)
    assert p["content"] == "Hello"


def test_get_nonexistent_post(conn):
    assert social_feed.get_post(conn, 999) is None


def test_delete_post(conn):
    pid = social_feed.create_post(conn, "alice", "Delete me")
    social_feed.delete_post(conn, pid)
    assert social_feed.get_post(conn, pid) is None


def test_react(conn):
    pid = social_feed.create_post(conn, "alice", "Post")
    rid = social_feed.react(conn, pid, "bob", "👍")
    assert rid > 0


def test_feed_includes_reactions(conn):
    pid = social_feed.create_post(conn, "alice", "Cool")
    social_feed.react(conn, pid, "bob", "👍")
    social_feed.react(conn, pid, "carol", "👍")
    feed = social_feed.get_feed(conn)
    assert feed[0]["reactions"]["👍"] == 2


def test_get_reactions(conn):
    pid = social_feed.create_post(conn, "alice", "Post")
    social_feed.react(conn, pid, "bob", "👍")
    reactions = social_feed.get_reactions(conn, pid)
    assert len(reactions) == 1


def test_filter_by_type(conn):
    social_feed.create_post(conn, "alice", "general")
    social_feed.share_win(conn, "alice", "Closed ticket")
    wins = social_feed.filter_by_type(conn, "win")
    assert len(wins) == 1


def test_filter_by_author(conn):
    social_feed.create_post(conn, "alice", "p1")
    social_feed.create_post(conn, "bob", "p2")
    alice_posts = social_feed.filter_by_author(conn, "alice")
    assert len(alice_posts) == 1


def test_share_win(conn):
    pid = social_feed.share_win(conn, "alice", "Shipped!")
    post = social_feed.get_post(conn, pid)
    assert post["post_type"] == "win"


def test_share_goal(conn):
    pid = social_feed.share_goal(conn, "alice", "Run 5k")
    post = social_feed.get_post(conn, pid)
    assert post["post_type"] == "goal"
