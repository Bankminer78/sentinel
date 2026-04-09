"""Tests for sentinel.book_notes."""
import pytest
from sentinel import book_notes as bn, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_note(conn):
    nid = bn.add_note(conn, "Atomic Habits", "Small improvements compound")
    assert nid > 0


def test_get_notes(conn):
    bn.add_note(conn, "Source A", "Note 1")
    bn.add_note(conn, "Source A", "Note 2")
    bn.add_note(conn, "Source B", "Note 3")
    assert len(bn.get_notes(conn, source="Source A")) == 2


def test_get_sources(conn):
    bn.add_note(conn, "Book A", "Note")
    bn.add_note(conn, "Book B", "Note")
    sources = bn.get_sources(conn)
    assert len(sources) == 2


def test_search_vault(conn):
    bn.add_note(conn, "Book", "Something important about focus")
    results = bn.search_vault(conn, "focus")
    assert len(results) == 1


def test_random_note_empty(conn):
    assert bn.random_note(conn) is None


def test_random_note(conn):
    bn.add_note(conn, "Book", "content")
    r = bn.random_note(conn)
    assert r is not None


def test_delete_note(conn):
    nid = bn.add_note(conn, "Book", "content")
    bn.delete_note(conn, nid)
    assert bn.note_count(conn) == 0


def test_note_types(conn):
    bn.add_note(conn, "Book", "content", note_type="insight")
    bn.add_note(conn, "Book", "content", note_type="quote")
    types = bn.note_types(conn)
    assert len(types) == 2


def test_note_count(conn):
    bn.add_note(conn, "Book", "Note")
    bn.add_note(conn, "Book", "Note")
    assert bn.note_count(conn) == 2


def test_get_notes_by_type(conn):
    bn.add_note(conn, "Book", "q1", note_type="quote")
    bn.add_note(conn, "Book", "i1", note_type="insight")
    quotes = bn.get_notes(conn, note_type="quote")
    assert len(quotes) == 1
