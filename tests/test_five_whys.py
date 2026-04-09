"""Tests for sentinel.five_whys."""
import pytest
from sentinel import five_whys as fw, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_start_analysis(conn):
    aid = fw.start_analysis(conn, "I'm always tired")
    assert aid > 0


def test_add_why(conn):
    aid = fw.start_analysis(conn, "I'm tired")
    result = fw.add_why(conn, aid, "I don't sleep enough")
    assert result["count"] == 1


def test_add_multiple_whys(conn):
    aid = fw.start_analysis(conn, "Problem")
    for why in ["W1", "W2", "W3", "W4", "W5"]:
        fw.add_why(conn, aid, why)
    analysis = fw.get_analysis(conn, aid)
    assert len(analysis["whys"]) == 5


def test_set_root_cause(conn):
    aid = fw.start_analysis(conn, "Problem")
    fw.set_root_cause(conn, aid, "Root cause")
    analysis = fw.get_analysis(conn, aid)
    assert analysis["root_cause"] == "Root cause"


def test_set_solution(conn):
    aid = fw.start_analysis(conn, "Problem")
    fw.set_solution(conn, aid, "Solution")
    analysis = fw.get_analysis(conn, aid)
    assert analysis["solution"] == "Solution"


def test_get_nonexistent(conn):
    assert fw.get_analysis(conn, 999) is None


def test_list_analyses(conn):
    fw.start_analysis(conn, "Problem 1")
    fw.start_analysis(conn, "Problem 2")
    assert len(fw.list_analyses(conn)) == 2


def test_delete_analysis(conn):
    aid = fw.start_analysis(conn, "Delete me")
    fw.delete_analysis(conn, aid)
    assert fw.get_analysis(conn, aid) is None


def test_incomplete_analyses(conn):
    fw.start_analysis(conn, "Incomplete")
    assert len(fw.incomplete_analyses(conn)) == 1


def test_with_solutions(conn):
    aid = fw.start_analysis(conn, "Solved")
    fw.set_solution(conn, aid, "Fix")
    assert len(fw.with_solutions(conn)) == 1


def test_add_why_nonexistent(conn):
    assert fw.add_why(conn, 999, "why") is None
