"""Tests for sentinel.chat_history."""
import pytest
from sentinel import chat_history, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_session(conn):
    sid = chat_history.create_session(conn, "Test chat")
    assert sid > 0


def test_add_message(conn):
    sid = chat_history.create_session(conn)
    mid = chat_history.add_message(conn, sid, "user", "Hello")
    assert mid > 0


def test_get_session(conn):
    sid = chat_history.create_session(conn, "Test")
    chat_history.add_message(conn, sid, "user", "Hi")
    chat_history.add_message(conn, sid, "assistant", "Hello!")
    session = chat_history.get_session(conn, sid)
    assert len(session["messages"]) == 2


def test_get_nonexistent(conn):
    assert chat_history.get_session(conn, 999) is None


def test_list_sessions(conn):
    chat_history.create_session(conn, "S1")
    chat_history.create_session(conn, "S2")
    sessions = chat_history.list_sessions(conn)
    assert len(sessions) == 2


def test_delete_session(conn):
    sid = chat_history.create_session(conn)
    chat_history.add_message(conn, sid, "user", "test")
    chat_history.delete_session(conn, sid)
    assert chat_history.get_session(conn, sid) is None


def test_get_messages(conn):
    sid = chat_history.create_session(conn)
    chat_history.add_message(conn, sid, "user", "m1")
    chat_history.add_message(conn, sid, "assistant", "m2")
    messages = chat_history.get_messages(conn, sid)
    assert len(messages) == 2


def test_rename_session(conn):
    sid = chat_history.create_session(conn, "Old")
    chat_history.rename_session(conn, sid, "New")
    session = chat_history.get_session(conn, sid)
    assert session["title"] == "New"


def test_search_history(conn):
    sid = chat_history.create_session(conn)
    chat_history.add_message(conn, sid, "user", "hello world")
    chat_history.add_message(conn, sid, "user", "goodbye")
    results = chat_history.search_history(conn, "hello")
    assert len(results) == 1


def test_get_session_context(conn):
    sid = chat_history.create_session(conn)
    for i in range(5):
        chat_history.add_message(conn, sid, "user", f"msg {i}")
    context = chat_history.get_session_context(conn, sid, max_messages=3)
    assert len(context) == 3


def test_empty_sessions(conn):
    assert chat_history.list_sessions(conn) == []
