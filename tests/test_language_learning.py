"""Tests for sentinel.language_learning."""
import pytest
from sentinel import language_learning as ll, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_language(conn):
    lid = ll.add_language(conn, "Spanish", "beginner")
    assert lid >= 0


def test_get_languages(conn):
    ll.add_language(conn, "Spanish")
    ll.add_language(conn, "French")
    assert len(ll.get_languages(conn)) == 2


def test_add_word(conn):
    wid = ll.add_word(conn, "Spanish", "hola", "hello")
    assert wid > 0


def test_get_words(conn):
    ll.add_word(conn, "Spanish", "hola", "hello")
    ll.add_word(conn, "Spanish", "adios", "goodbye")
    assert len(ll.get_words(conn, language="Spanish")) == 2


def test_review_word_correct(conn):
    wid = ll.add_word(conn, "Spanish", "hola", "hello")
    ll.review_word(conn, wid, True)
    words = ll.get_words(conn)
    assert words[0]["mastery"] == 1


def test_review_word_incorrect(conn):
    wid = ll.add_word(conn, "Spanish", "hola", "hello")
    ll.review_word(conn, wid, False)
    words = ll.get_words(conn)
    assert words[0]["mastery"] == 0


def test_due_for_review(conn):
    ll.add_word(conn, "Spanish", "hola", "hello")
    due = ll.due_for_review(conn)
    assert len(due) == 1


def test_log_session(conn):
    sid = ll.log_session(conn, "Spanish", 30, "study")
    assert sid > 0


def test_total_minutes(conn):
    ll.log_session(conn, "Spanish", 30)
    ll.log_session(conn, "Spanish", 15)
    assert ll.total_minutes(conn, "Spanish") == 45


def test_streak_empty(conn):
    assert ll.streak(conn, "Spanish") == 0


def test_streak(conn):
    ll.log_session(conn, "Spanish", 10)
    assert ll.streak(conn, "Spanish") >= 1


def test_vocabulary_count(conn):
    ll.add_word(conn, "Spanish", "w1", "t1")
    ll.add_word(conn, "Spanish", "w2", "t2")
    assert ll.vocabulary_count(conn, "Spanish") == 2


def test_mastery_stats(conn):
    ll.add_word(conn, "Spanish", "w1", "t1")
    stats = ll.mastery_stats(conn, "Spanish")
    assert 0 in stats
