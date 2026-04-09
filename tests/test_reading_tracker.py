"""Tests for sentinel.reading_tracker."""
import pytest
from sentinel import reading_tracker as rt, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_book(conn):
    bid = rt.add_book(conn, "Dune", "Frank Herbert", 800)
    assert bid > 0


def test_get_books(conn):
    rt.add_book(conn, "Book 1")
    rt.add_book(conn, "Book 2")
    assert len(rt.get_books(conn)) == 2


def test_get_books_by_status(conn):
    bid = rt.add_book(conn, "Test")
    rt.finish_book(conn, bid)
    assert len(rt.get_books(conn, "finished")) == 1
    assert len(rt.get_books(conn, "reading")) == 0


def test_get_book(conn):
    bid = rt.add_book(conn, "Test", "Author")
    book = rt.get_book(conn, bid)
    assert book["title"] == "Test"


def test_log_reading(conn):
    bid = rt.add_book(conn, "Test", "", 100)
    rt.log_reading(conn, bid, 20, 30)
    book = rt.get_book(conn, bid)
    assert book["current_page"] == 20


def test_finish_book(conn):
    bid = rt.add_book(conn, "Test")
    rt.finish_book(conn, bid)
    assert rt.get_book(conn, bid)["status"] == "finished"


def test_add_note(conn):
    bid = rt.add_book(conn, "Test")
    nid = rt.add_note(conn, bid, 50, "Great quote")
    assert nid > 0


def test_get_notes(conn):
    bid = rt.add_book(conn, "Test")
    rt.add_note(conn, bid, 10, "Note 1")
    rt.add_note(conn, bid, 20, "Note 2")
    notes = rt.get_notes(conn, bid)
    assert len(notes) == 2


def test_total_pages_read(conn):
    bid = rt.add_book(conn, "Test")
    rt.log_reading(conn, bid, 50, 30)
    assert rt.total_pages_read(conn) == 50


def test_reading_streak_empty(conn):
    assert rt.reading_streak(conn) == 0


def test_reading_streak_today(conn):
    bid = rt.add_book(conn, "Test")
    rt.log_reading(conn, bid, 10, 15)
    assert rt.reading_streak(conn) >= 1


def test_books_finished_this_year(conn):
    bid = rt.add_book(conn, "Test")
    rt.finish_book(conn, bid)
    assert rt.books_finished_this_year(conn) == 1
