"""Tests for sentinel.rule_deps."""
import pytest
from sentinel import rule_deps, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_dependency(conn):
    db.add_rule(conn, "Parent")
    db.add_rule(conn, "Child")
    dep_id = rule_deps.add_dependency(conn, 1, 2)
    assert dep_id > 0


def test_get_children(conn):
    db.add_rule(conn, "Parent")
    db.add_rule(conn, "Child1")
    db.add_rule(conn, "Child2")
    rule_deps.add_dependency(conn, 1, 2)
    rule_deps.add_dependency(conn, 1, 3)
    children = rule_deps.get_children(conn, 1)
    assert len(children) == 2


def test_get_parents(conn):
    db.add_rule(conn, "P1")
    db.add_rule(conn, "P2")
    db.add_rule(conn, "Child")
    rule_deps.add_dependency(conn, 1, 3)
    rule_deps.add_dependency(conn, 2, 3)
    parents = rule_deps.get_parents(conn, 3)
    assert len(parents) == 2


def test_remove_dependency(conn):
    db.add_rule(conn, "P")
    db.add_rule(conn, "C")
    dep_id = rule_deps.add_dependency(conn, 1, 2)
    rule_deps.remove_dependency(conn, dep_id)
    assert rule_deps.get_children(conn, 1) == []


def test_list_all_deps(conn):
    db.add_rule(conn, "A")
    db.add_rule(conn, "B")
    db.add_rule(conn, "C")
    rule_deps.add_dependency(conn, 1, 2)
    rule_deps.add_dependency(conn, 2, 3)
    all_deps = rule_deps.list_all_deps(conn)
    assert len(all_deps) == 2


def test_cascade_activate(conn):
    db.add_rule(conn, "Parent")
    db.add_rule(conn, "Child")
    db.toggle_rule(conn, 2)  # Deactivate child
    rule_deps.add_dependency(conn, 1, 2, "activate")
    affected = rule_deps.resolve_cascade(conn, 1, True)
    assert 2 in affected
    # Verify child is active
    child = conn.execute("SELECT active FROM rules WHERE id=2").fetchone()
    assert child["active"] == 1


def test_cascade_deactivate(conn):
    db.add_rule(conn, "Parent")
    db.add_rule(conn, "Child")
    rule_deps.add_dependency(conn, 1, 2, "deactivate")
    affected = rule_deps.resolve_cascade(conn, 1, True)
    # child was active, now deactivated
    assert 2 in affected
    child = conn.execute("SELECT active FROM rules WHERE id=2").fetchone()
    assert child["active"] == 0


def test_cascade_no_change(conn):
    db.add_rule(conn, "Parent")
    db.add_rule(conn, "Child")  # Already active
    rule_deps.add_dependency(conn, 1, 2, "activate")
    affected = rule_deps.resolve_cascade(conn, 1, True)
    assert affected == []  # No change needed


def test_cascade_nonexistent_child(conn):
    db.add_rule(conn, "Parent")
    rule_deps.add_dependency(conn, 1, 999)
    affected = rule_deps.resolve_cascade(conn, 1, True)
    assert affected == []


def test_action_default_activate(conn):
    db.add_rule(conn, "P")
    db.add_rule(conn, "C")
    rule_deps.add_dependency(conn, 1, 2)  # Default action
    children = rule_deps.get_children(conn, 1)
    assert children[0]["action"] == "activate"
