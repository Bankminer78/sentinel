"""Tests for sentinel.identity_tracker."""
import pytest
from sentinel import identity_tracker as it, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_identity(conn):
    iid = it.add_identity(conn, "writer")
    assert iid > 0


def test_get_identities(conn):
    it.add_identity(conn, "writer")
    it.add_identity(conn, "runner")
    assert len(it.get_identities(conn)) == 2


def test_cast_vote(conn):
    iid = it.add_identity(conn, "writer")
    vid = it.cast_vote(conn, iid, "wrote 500 words")
    assert vid > 0


def test_votes_count(conn):
    iid = it.add_identity(conn, "writer")
    it.cast_vote(conn, iid, "action 1")
    it.cast_vote(conn, iid, "action 2")
    assert it.votes_count(conn, iid) == 2


def test_deactivate(conn):
    iid = it.add_identity(conn, "test")
    it.deactivate(conn, iid)
    assert len(it.get_identities(conn)) == 0


def test_delete(conn):
    iid = it.add_identity(conn, "test")
    it.delete_identity(conn, iid)
    assert len(it.get_identities(conn, active_only=False)) == 0


def test_get_recent_votes(conn):
    iid = it.add_identity(conn, "writer")
    it.cast_vote(conn, iid, "a1")
    it.cast_vote(conn, iid, "a2")
    votes = it.get_recent_votes(conn, iid)
    assert len(votes) == 2


def test_votes_today(conn):
    iid = it.add_identity(conn, "writer")
    it.cast_vote(conn, iid, "today's action")
    assert it.votes_today(conn, iid) == 1


def test_identity_progress(conn):
    iid = it.add_identity(conn, "writer", "I am a writer")
    it.cast_vote(conn, iid, "wrote")
    progress = it.identity_progress(conn, iid)
    assert progress["identity"] == "writer"
    assert progress["today"] == 1


def test_all_identities_progress(conn):
    it.add_identity(conn, "writer")
    it.add_identity(conn, "runner")
    assert len(it.all_identities_progress(conn)) == 2


def test_streak(conn):
    iid = it.add_identity(conn, "writer")
    it.cast_vote(conn, iid, "today")
    assert it.streak(conn, iid) >= 1
