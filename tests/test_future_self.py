"""Tests for sentinel.future_self."""
import pytest
from sentinel import future_self as fs, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_write_letter(conn):
    lid = fs.write_letter(conn, "Dear future me...", deliver_in_days=30)
    assert lid > 0


def test_get_letter(conn):
    lid = fs.write_letter(conn, "Test content")
    letter = fs.get_letter(conn, lid)
    assert letter["content"] == "Test content"


def test_list_letters(conn):
    fs.write_letter(conn, "Letter 1")
    fs.write_letter(conn, "Letter 2")
    assert len(fs.list_letters(conn)) == 2


def test_deliverable_today(conn):
    lid = fs.write_letter(conn, "Past", deliver_in_days=-10)
    deliverable = fs.deliverable_today(conn)
    assert len(deliverable) >= 1


def test_open_letter(conn):
    lid = fs.write_letter(conn, "Past", deliver_in_days=-1)
    letter = fs.open_letter(conn, lid)
    assert letter["delivered"] == 1


def test_delete_letter(conn):
    lid = fs.write_letter(conn, "Delete")
    fs.delete_letter(conn, lid)
    assert fs.get_letter(conn, lid) is None


def test_pending_letters(conn):
    fs.write_letter(conn, "Pending")
    assert len(fs.pending_letters(conn)) == 1


def test_opened_letters(conn):
    lid = fs.write_letter(conn, "Test", deliver_in_days=-1)
    fs.open_letter(conn, lid)
    assert len(fs.opened_letters(conn)) == 1


def test_count_pending(conn):
    fs.write_letter(conn, "L1")
    fs.write_letter(conn, "L2")
    assert fs.count_pending(conn) == 2


def test_days_until_delivery(conn):
    lid = fs.write_letter(conn, "Future", deliver_in_days=30)
    days = fs.days_until_delivery(conn, lid)
    assert 29 <= days <= 30
