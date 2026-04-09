"""Tests for sentinel.vision_board."""
import pytest
from sentinel import vision_board as vb, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_item(conn):
    iid = vb.add_item(conn, "quote", "Stay focused", priority=5)
    assert iid > 0


def test_get_items(conn):
    vb.add_item(conn, "quote", "Q1")
    vb.add_item(conn, "image", "image.jpg")
    assert len(vb.get_items(conn)) == 2


def test_get_items_by_type(conn):
    vb.add_item(conn, "quote", "Q1")
    vb.add_item(conn, "image", "img.jpg")
    assert len(vb.get_items(conn, item_type="quote")) == 1


def test_get_item(conn):
    iid = vb.add_item(conn, "goal", "Run marathon")
    item = vb.get_item(conn, iid)
    assert item["content"] == "Run marathon"


def test_delete_item(conn):
    iid = vb.add_item(conn, "quote", "Delete")
    vb.delete_item(conn, iid)
    assert vb.get_item(conn, iid) is None


def test_update_priority(conn):
    iid = vb.add_item(conn, "quote", "Low")
    vb.update_priority(conn, iid, 10)
    assert vb.get_item(conn, iid)["priority"] == 10


def test_top_items(conn):
    vb.add_item(conn, "quote", "Low", priority=1)
    vb.add_item(conn, "quote", "High", priority=10)
    top = vb.top_items(conn)
    assert top[0]["content"] == "High"


def test_random_affirmation_empty(conn):
    assert vb.random_affirmation(conn) is None


def test_random_affirmation(conn):
    vb.add_item(conn, "affirmation", "I am capable")
    a = vb.random_affirmation(conn)
    assert a["content"] == "I am capable"


def test_categories(conn):
    vb.add_item(conn, "quote", "Q", category="work")
    vb.add_item(conn, "quote", "Q", category="life")
    cats = vb.categories(conn)
    assert len(cats) == 2


def test_count_items(conn):
    vb.add_item(conn, "quote", "Q1")
    vb.add_item(conn, "quote", "Q2")
    assert vb.count_items(conn) == 2


def test_list_item_types():
    types = vb.list_item_types()
    assert "quote" in types
    assert "affirmation" in types
