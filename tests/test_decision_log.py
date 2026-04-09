"""Tests for sentinel.decision_log."""
import pytest
from sentinel import decision_log as dl, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_log_decision(conn):
    did = dl.log_decision(conn, "Buy car", "Need transport",
                          ["Used Honda", "New Toyota"], "Used Honda", "Cheaper")
    assert did > 0


def test_get_decision(conn):
    did = dl.log_decision(conn, "Test", "ctx", ["a", "b"], "a")
    d = dl.get_decision(conn, did)
    assert d["title"] == "Test"
    assert d["options"] == ["a", "b"]


def test_list_decisions(conn):
    dl.log_decision(conn, "D1", "", [], "")
    dl.log_decision(conn, "D2", "", [], "")
    assert len(dl.list_decisions(conn)) == 2


def test_update_outcome(conn):
    did = dl.log_decision(conn, "Test", "", [], "chose")
    dl.update_outcome(conn, did, "Great outcome", 9)
    d = dl.get_decision(conn, did)
    assert d["outcome_rating"] == 9


def test_delete_decision(conn):
    did = dl.log_decision(conn, "Del", "", [], "")
    dl.delete_decision(conn, did)
    assert dl.get_decision(conn, did) is None


def test_unreviewed(conn):
    dl.log_decision(conn, "Unreviewed", "", [], "")
    assert len(dl.unreviewed_decisions(conn)) == 1


def test_search(conn):
    dl.log_decision(conn, "Buy car", "transport", [], "")
    results = dl.search_decisions(conn, "car")
    assert len(results) == 1


def test_rating_stats(conn):
    did1 = dl.log_decision(conn, "D1", "", [], "")
    did2 = dl.log_decision(conn, "D2", "", [], "")
    dl.update_outcome(conn, did1, "good", 8)
    dl.update_outcome(conn, did2, "great", 10)
    stats = dl.rating_stats(conn)
    assert stats["count"] == 2
    assert stats["avg_rating"] == 9.0


def test_get_nonexistent(conn):
    assert dl.get_decision(conn, 999) is None
