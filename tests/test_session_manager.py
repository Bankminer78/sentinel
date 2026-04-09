"""Tests for sentinel.session_manager."""
import pytest
from sentinel import session_manager as sm


@pytest.fixture(autouse=True)
def clear_sessions():
    sm.clear_all()
    yield
    sm.clear_all()


def test_create_session():
    sid = sm.create_session("alice")
    assert sid


def test_get_session():
    sid = sm.create_session("bob")
    s = sm.get_session(sid)
    assert s["user"] == "bob"


def test_is_valid():
    sid = sm.create_session("alice")
    assert sm.is_valid(sid) is True


def test_is_valid_false():
    assert sm.is_valid("nonexistent") is False


def test_touch_session():
    sid = sm.create_session("alice")
    sm.touch_session(sid)  # Should not raise


def test_destroy_session():
    sid = sm.create_session("alice")
    sm.destroy_session(sid)
    assert sm.is_valid(sid) is False


def test_list_sessions():
    sm.create_session("alice")
    sm.create_session("bob")
    assert len(sm.list_sessions()) == 2


def test_list_sessions_by_user():
    sm.create_session("alice")
    sm.create_session("alice")
    sm.create_session("bob")
    assert len(sm.list_sessions(user="alice")) == 2


def test_set_get_data():
    sid = sm.create_session("alice")
    sm.set_data(sid, "key", "value")
    assert sm.get_data(sid, "key") == "value"


def test_get_data_default():
    sid = sm.create_session("alice")
    assert sm.get_data(sid, "missing", "default") == "default"


def test_session_count():
    sm.create_session("a")
    sm.create_session("b")
    assert sm.session_count() == 2


def test_extend_session():
    sid = sm.create_session("alice")
    assert sm.extend_session(sid, 48) is True


def test_extend_nonexistent():
    assert sm.extend_session("ghost") is False
