"""Tests for sentinel.learnings."""
import pytest
from sentinel import learnings, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_learning(conn):
    lid = learnings.add_learning(conn, "Learned Python generators", "tech")
    assert lid > 0


def test_get_learnings(conn):
    learnings.add_learning(conn, "L1")
    learnings.add_learning(conn, "L2")
    assert len(learnings.get_learnings(conn)) == 2


def test_today_learnings(conn):
    learnings.add_learning(conn, "Today's lesson")
    assert len(learnings.today_learnings(conn)) == 1


def test_weekly_learnings(conn):
    learnings.add_learning(conn, "L1")
    assert len(learnings.weekly_learnings(conn)) >= 1


def test_delete(conn):
    lid = learnings.add_learning(conn, "Delete me")
    learnings.delete_learning(conn, lid)
    assert learnings.get_learnings(conn) == []


def test_search(conn):
    learnings.add_learning(conn, "Learned about Python decorators")
    results = learnings.search_learnings(conn, "decorators")
    assert len(results) == 1


def test_count_by_category(conn):
    learnings.add_learning(conn, "L1", "tech")
    learnings.add_learning(conn, "L2", "tech")
    learnings.add_learning(conn, "L3", "life")
    counts = learnings.count_by_category(conn)
    assert counts["tech"] == 2


def test_streak_empty(conn):
    assert learnings.learning_streak(conn) == 0


def test_streak_today(conn):
    learnings.add_learning(conn, "Today")
    assert learnings.learning_streak(conn) >= 1


def test_total(conn):
    learnings.add_learning(conn, "L1")
    learnings.add_learning(conn, "L2")
    assert learnings.total_learnings(conn) == 2
