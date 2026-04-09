"""Tests for sentinel.review_system."""
import pytest
from sentinel import review_system as rs, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_review(conn):
    rid = rs.create_review(conn, "daily", "Good day", "Shipped feature")
    assert rid > 0


def test_create_invalid_type(conn):
    assert rs.create_review(conn, "invalid") == 0


def test_get_review(conn):
    rid = rs.create_review(conn, "daily", "Reflections")
    r = rs.get_review(conn, rid)
    assert r["review_type"] == "daily"


def test_current_review(conn):
    rs.create_review(conn, "daily", "Today")
    current = rs.current_review(conn, "daily")
    assert current is not None


def test_list_reviews(conn):
    rs.create_review(conn, "daily", "R1")
    rs.create_review(conn, "daily", "R2")
    reviews = rs.list_reviews(conn, "daily")
    assert len(reviews) == 2


def test_has_reviewed(conn):
    rs.create_review(conn, "daily")
    assert rs.has_reviewed(conn, "daily") is True
    assert rs.has_reviewed(conn, "weekly") is False


def test_delete_review(conn):
    rid = rs.create_review(conn, "daily")
    rs.delete_review(conn, rid)
    assert rs.get_review(conn, rid) is None


def test_overdue_reviews(conn):
    rs.create_review(conn, "daily")
    overdue = rs.overdue_reviews(conn)
    assert "daily" not in overdue
    assert "weekly" in overdue


def test_review_streak(conn):
    rs.create_review(conn, "daily")
    assert rs.review_streak(conn) >= 1


def test_review_streak_nonexistent(conn):
    assert rs.review_streak(conn, "weekly") == 0


def test_list_review_types():
    types = rs.list_review_types()
    assert "daily" in types
    assert len(types) == 5


def test_total_reviews(conn):
    rs.create_review(conn, "daily")
    rs.create_review(conn, "weekly")
    assert rs.total_reviews(conn) == 2
