"""Tests for sentinel.questions."""
import pytest
from sentinel import questions as q, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_question(conn):
    qid = q.add_question(conn, "What should I do?", "life")
    assert qid > 0


def test_get_questions(conn):
    q.add_question(conn, "Q1")
    q.add_question(conn, "Q2")
    assert len(q.get_questions(conn)) == 2


def test_answer_question(conn):
    qid = q.add_question(conn, "Q?")
    q.answer_question(conn, qid, "A.")
    assert q.get_question(conn, qid)["answer"] == "A."


def test_unanswered(conn):
    q.add_question(conn, "Q1")
    assert len(q.unanswered(conn)) == 1


def test_answered(conn):
    qid = q.add_question(conn, "Q?")
    q.answer_question(conn, qid, "A")
    assert len(q.answered(conn)) == 1


def test_delete(conn):
    qid = q.add_question(conn, "Q")
    q.delete_question(conn, qid)
    assert q.get_question(conn, qid) is None


def test_categories(conn):
    q.add_question(conn, "Q1", "cat1")
    q.add_question(conn, "Q2", "cat2")
    cats = q.categories(conn)
    assert len(cats) == 2


def test_search(conn):
    q.add_question(conn, "What is meaning?")
    results = q.search_questions(conn, "meaning")
    assert len(results) == 1


def test_oldest_unanswered(conn):
    q.add_question(conn, "First")
    import time
    time.sleep(0.01)
    q.add_question(conn, "Second")
    oldest = q.oldest_unanswered(conn)
    assert oldest["question"] == "First"


def test_no_oldest(conn):
    assert q.oldest_unanswered(conn) is None
