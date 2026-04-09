"""Tests for sentinel.kanban."""
import pytest
from sentinel import kanban, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_board(conn):
    bid = kanban.create_board(conn, "Project A")
    assert bid > 0


def test_get_boards(conn):
    kanban.create_board(conn, "B1")
    kanban.create_board(conn, "B2")
    boards = kanban.get_boards(conn)
    assert len(boards) == 2


def test_add_card(conn):
    bid = kanban.create_board(conn, "Test")
    cid = kanban.add_card(conn, bid, "Task 1")
    assert cid > 0


def test_get_cards(conn):
    bid = kanban.create_board(conn, "Test")
    kanban.add_card(conn, bid, "C1")
    kanban.add_card(conn, bid, "C2")
    assert len(kanban.get_cards(conn, bid)) == 2


def test_get_cards_by_column(conn):
    bid = kanban.create_board(conn, "Test")
    kanban.add_card(conn, bid, "Card", column="todo")
    assert len(kanban.get_cards(conn, bid, column="todo")) == 1
    assert len(kanban.get_cards(conn, bid, column="done")) == 0


def test_move_card(conn):
    bid = kanban.create_board(conn, "Test")
    cid = kanban.add_card(conn, bid, "Task")
    kanban.move_card(conn, cid, "done")
    cards = kanban.get_cards(conn, bid, column="done")
    assert len(cards) == 1


def test_delete_card(conn):
    bid = kanban.create_board(conn, "Test")
    cid = kanban.add_card(conn, bid, "Task")
    kanban.delete_card(conn, cid)
    assert kanban.get_cards(conn, bid) == []


def test_update_card(conn):
    bid = kanban.create_board(conn, "Test")
    cid = kanban.add_card(conn, bid, "Old title")
    kanban.update_card(conn, cid, title="New title", priority=5)
    cards = kanban.get_cards(conn, bid)
    assert cards[0]["title"] == "New title"
    assert cards[0]["priority"] == 5


def test_board_summary(conn):
    bid = kanban.create_board(conn, "Test")
    kanban.add_card(conn, bid, "T1", column="todo")
    kanban.add_card(conn, bid, "T2", column="done")
    summary = kanban.board_summary(conn, bid)
    assert summary["total"] == 2
    assert summary["completed"] == 1


def test_delete_board(conn):
    bid = kanban.create_board(conn, "Test")
    kanban.add_card(conn, bid, "Task")
    kanban.delete_board(conn, bid)
    assert kanban.get_boards(conn) == []


def test_priority_sort(conn):
    bid = kanban.create_board(conn, "Test")
    kanban.add_card(conn, bid, "Low", priority=1)
    kanban.add_card(conn, bid, "High", priority=10)
    cards = kanban.get_cards(conn, bid)
    assert cards[0]["title"] == "High"
