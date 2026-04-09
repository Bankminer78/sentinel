"""Tests for sentinel.macros."""
import pytest
from sentinel import macros, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_macro(conn):
    mid = macros.create_macro(conn, "morning", [{"action": "coffee"}], "Morning routine")
    assert mid > 0


def test_get_macros(conn):
    macros.create_macro(conn, "m1", [{"action": "a1"}])
    macros.create_macro(conn, "m2", [{"action": "a2"}])
    assert len(macros.get_macros(conn)) == 2


def test_get_macro(conn):
    mid = macros.create_macro(conn, "test", [{"action": "x"}])
    m = macros.get_macro(conn, mid)
    assert m["name"] == "test"
    assert m["actions"] == [{"action": "x"}]


def test_get_by_name(conn):
    macros.create_macro(conn, "named", [{"action": "x"}])
    m = macros.get_macro_by_name(conn, "named")
    assert m is not None
    assert m["name"] == "named"


def test_get_by_name_nonexistent(conn):
    assert macros.get_macro_by_name(conn, "ghost") is None


def test_delete_macro(conn):
    mid = macros.create_macro(conn, "del", [{}])
    macros.delete_macro(conn, mid)
    assert macros.get_macros(conn) == []


def test_log_run(conn):
    mid = macros.create_macro(conn, "test", [{}])
    rid = macros.log_run(conn, mid, "success")
    assert rid > 0


def test_get_run_history(conn):
    mid = macros.create_macro(conn, "test", [{}])
    macros.log_run(conn, mid)
    macros.log_run(conn, mid)
    assert len(macros.get_run_history(conn, mid)) == 2


def test_total_macros(conn):
    macros.create_macro(conn, "m1", [])
    macros.create_macro(conn, "m2", [])
    assert macros.total_macros(conn) == 2


def test_update_macro(conn):
    mid = macros.create_macro(conn, "test", [{"action": "old"}])
    macros.update_macro(conn, mid, actions=[{"action": "new"}])
    m = macros.get_macro(conn, mid)
    assert m["actions"] == [{"action": "new"}]


def test_update_description(conn):
    mid = macros.create_macro(conn, "test", [{}], description="old desc")
    macros.update_macro(conn, mid, description="new desc")
    m = macros.get_macro(conn, mid)
    assert m["description"] == "new desc"
