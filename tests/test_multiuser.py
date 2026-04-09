"""Tests for sentinel.multiuser."""
import pytest
from sentinel import multiuser, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_user(conn):
    uid = multiuser.create_user(conn, "alice")
    assert uid > 0


def test_create_duplicate(conn):
    uid1 = multiuser.create_user(conn, "alice")
    uid2 = multiuser.create_user(conn, "alice")
    # UNIQUE constraint returns same user
    users = multiuser.list_users(conn)
    assert len(users) == 1


def test_list_users_empty(conn):
    assert multiuser.list_users(conn) == []


def test_list_users(conn):
    multiuser.create_user(conn, "alice")
    multiuser.create_user(conn, "bob")
    users = multiuser.list_users(conn)
    assert len(users) == 2


def test_switch_user(conn):
    uid = multiuser.create_user(conn, "alice")
    assert multiuser.switch_user(conn, uid) is True
    current = multiuser.get_current_user(conn)
    assert current["name"] == "alice"


def test_switch_nonexistent(conn):
    assert multiuser.switch_user(conn, 999) is False


def test_get_current_user_default(conn):
    current = multiuser.get_current_user(conn)
    assert current["name"] == "default"


def test_delete_user(conn):
    uid = multiuser.create_user(conn, "alice")
    multiuser.delete_user(conn, uid)
    assert multiuser.list_users(conn) == []


def test_delete_current_user_clears(conn):
    uid = multiuser.create_user(conn, "alice")
    multiuser.switch_user(conn, uid)
    multiuser.delete_user(conn, uid)
    current = multiuser.get_current_user(conn)
    assert current["name"] == "default"


def test_user_stats(conn):
    uid = multiuser.create_user(conn, "alice")
    stats = multiuser.user_stats(conn, uid)
    assert stats["name"] == "alice"


def test_user_stats_nonexistent(conn):
    assert multiuser.user_stats(conn, 999) == {}


def test_users_sorted(conn):
    multiuser.create_user(conn, "charlie")
    multiuser.create_user(conn, "alice")
    multiuser.create_user(conn, "bob")
    users = multiuser.list_users(conn)
    names = [u["name"] for u in users]
    assert names == ["alice", "bob", "charlie"]
