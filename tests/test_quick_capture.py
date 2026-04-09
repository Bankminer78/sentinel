"""Tests for sentinel.quick_capture."""
import pytest
from sentinel import quick_capture as qc, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_capture(conn):
    iid = qc.capture(conn, "Test item", "task")
    assert iid > 0


def test_capture_invalid_type(conn):
    iid = qc.capture(conn, "Test", "invalid_type")
    inbox = qc.get_inbox(conn)
    assert inbox[0]["item_type"] == "other"


def test_get_inbox(conn):
    qc.capture(conn, "Item 1")
    qc.capture(conn, "Item 2")
    assert len(qc.get_inbox(conn)) == 2


def test_mark_processed(conn):
    iid = qc.capture(conn, "Process me")
    qc.mark_processed(conn, iid)
    assert len(qc.get_inbox(conn, unprocessed_only=True)) == 0


def test_delete_item(conn):
    iid = qc.capture(conn, "Delete me")
    qc.delete_item(conn, iid)
    assert qc.total_captured(conn) == 0


def test_process_all(conn):
    qc.capture(conn, "Item 1")
    qc.capture(conn, "Item 2")
    qc.process_all(conn)
    assert qc.unprocessed_count(conn) == 0


def test_by_type(conn):
    qc.capture(conn, "Task 1", "task")
    qc.capture(conn, "Note 1", "note")
    assert len(qc.by_type(conn, "task")) == 1


def test_unprocessed_count(conn):
    qc.capture(conn, "Item 1")
    qc.capture(conn, "Item 2")
    assert qc.unprocessed_count(conn) == 2


def test_search_inbox(conn):
    qc.capture(conn, "Important idea about project")
    results = qc.search_inbox(conn, "project")
    assert len(results) == 1


def test_total_captured(conn):
    qc.capture(conn, "Item 1")
    qc.capture(conn, "Item 2")
    assert qc.total_captured(conn) == 2


def test_list_types():
    types = qc.list_types()
    assert "task" in types
    assert "note" in types
