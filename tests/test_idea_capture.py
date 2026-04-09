"""Tests for sentinel.idea_capture."""
import pytest
from sentinel import idea_capture as ic, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_capture(conn):
    iid = ic.capture(conn, "Great idea", tags=["business", "tech"])
    assert iid > 0


def test_get_ideas(conn):
    ic.capture(conn, "Idea 1")
    ic.capture(conn, "Idea 2")
    assert len(ic.get_ideas(conn)) == 2


def test_get_unreviewed(conn):
    ic.capture(conn, "Idea 1")
    assert len(ic.get_ideas(conn, unreviewed_only=True)) == 1


def test_star_idea(conn):
    iid = ic.capture(conn, "Star this")
    ic.star_idea(conn, iid)
    starred = ic.starred_ideas(conn)
    assert len(starred) == 1


def test_unstar(conn):
    iid = ic.capture(conn, "Star then unstar")
    ic.star_idea(conn, iid)
    ic.unstar_idea(conn, iid)
    assert len(ic.starred_ideas(conn)) == 0


def test_mark_reviewed(conn):
    iid = ic.capture(conn, "Review me")
    ic.mark_reviewed(conn, iid)
    assert len(ic.get_ideas(conn, unreviewed_only=True)) == 0


def test_delete(conn):
    iid = ic.capture(conn, "Delete me")
    ic.delete_idea(conn, iid)
    assert ic.count(conn) == 0


def test_search(conn):
    ic.capture(conn, "AI productivity app")
    ic.capture(conn, "Cooking recipe")
    results = ic.search_ideas(conn, "AI")
    assert len(results) == 1


def test_ideas_by_tag(conn):
    ic.capture(conn, "Idea 1", tags=["tech"])
    ic.capture(conn, "Idea 2", tags=["business"])
    tech = ic.ideas_by_tag(conn, "tech")
    assert len(tech) == 1


def test_count(conn):
    for i in range(5):
        ic.capture(conn, f"Idea {i}")
    assert ic.count(conn) == 5


def test_count_unreviewed(conn):
    iid1 = ic.capture(conn, "Idea 1")
    ic.capture(conn, "Idea 2")
    ic.mark_reviewed(conn, iid1)
    assert ic.count_unreviewed(conn) == 1
