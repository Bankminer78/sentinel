"""Tests for sentinel.mindmap."""
import pytest
from sentinel import mindmap as mm, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_mindmap(conn):
    mid = mm.create_mindmap(conn, "Project Plan")
    assert mid > 0


def test_add_node(conn):
    mid = mm.create_mindmap(conn, "Test")
    m = mm.get_mindmap(conn, mid)
    root_id = m["root_node_id"]
    nid = mm.add_node(conn, mid, root_id, "Child node")
    assert nid > 0


def test_get_mindmap(conn):
    mid = mm.create_mindmap(conn, "Test")
    m = mm.get_mindmap(conn, mid)
    assert m["title"] == "Test"
    assert "nodes" in m


def test_get_children(conn):
    mid = mm.create_mindmap(conn, "Test")
    m = mm.get_mindmap(conn, mid)
    root_id = m["root_node_id"]
    mm.add_node(conn, mid, root_id, "Child 1")
    mm.add_node(conn, mid, root_id, "Child 2")
    children = mm.get_children(conn, root_id)
    assert len(children) == 2


def test_delete_node(conn):
    mid = mm.create_mindmap(conn, "Test")
    m = mm.get_mindmap(conn, mid)
    root_id = m["root_node_id"]
    nid = mm.add_node(conn, mid, root_id, "To delete")
    mm.delete_node(conn, nid)
    assert len(mm.get_children(conn, root_id)) == 0


def test_delete_mindmap(conn):
    mid = mm.create_mindmap(conn, "Delete")
    mm.delete_mindmap(conn, mid)
    assert mm.get_mindmap(conn, mid) is None


def test_list_mindmaps(conn):
    mm.create_mindmap(conn, "M1")
    mm.create_mindmap(conn, "M2")
    assert len(mm.list_mindmaps(conn)) == 2


def test_update_node(conn):
    mid = mm.create_mindmap(conn, "Test")
    m = mm.get_mindmap(conn, mid)
    root_id = m["root_node_id"]
    mm.update_node(conn, root_id, "Updated")
    m2 = mm.get_mindmap(conn, mid)
    root = next(n for n in m2["nodes"] if n["id"] == root_id)
    assert root["content"] == "Updated"


def test_render_ascii(conn):
    mid = mm.create_mindmap(conn, "Test Plan")
    m = mm.get_mindmap(conn, mid)
    root_id = m["root_node_id"]
    mm.add_node(conn, mid, root_id, "Phase 1")
    mm.add_node(conn, mid, root_id, "Phase 2")
    ascii_render = mm.render_ascii(conn, mid)
    assert "Test Plan" in ascii_render
    assert "Phase 1" in ascii_render


def test_count_nodes(conn):
    mid = mm.create_mindmap(conn, "Test")
    m = mm.get_mindmap(conn, mid)
    root_id = m["root_node_id"]
    mm.add_node(conn, mid, root_id, "N1")
    mm.add_node(conn, mid, root_id, "N2")
    assert mm.count_nodes(conn, mid) == 3  # root + 2 children
