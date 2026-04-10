"""Tests for sentinel.imessage — chat.db sensor.

Most tests use a synthetic chat.db built in a temp dir to verify the SQL
shape works without depending on the real ~/Library/Messages/chat.db
(which requires Full Disk Access and is unstable across macOS versions).
"""
import sqlite3
from pathlib import Path
from unittest.mock import patch
import pytest

from sentinel import imessage


@pytest.fixture
def fake_chat_db(tmp_path):
    """Build a minimal chat.db with the columns imessage.py reads."""
    p = tmp_path / "chat.db"
    c = sqlite3.connect(str(p))
    c.executescript("""
        CREATE TABLE handle (
            ROWID INTEGER PRIMARY KEY,
            id TEXT,
            service TEXT
        );
        CREATE TABLE chat (
            ROWID INTEGER PRIMARY KEY,
            style INTEGER
        );
        CREATE TABLE message (
            ROWID INTEGER PRIMARY KEY,
            text TEXT,
            handle_id INTEGER,
            is_from_me INTEGER,
            date INTEGER
        );
        CREATE TABLE chat_message_join (
            chat_id INTEGER,
            message_id INTEGER
        );
        CREATE TABLE chat_handle_join (
            chat_id INTEGER,
            handle_id INTEGER
        );
    """)
    # Two handles
    c.execute("INSERT INTO handle (ROWID, id, service) VALUES (1, '+15551234567', 'iMessage')")
    c.execute("INSERT INTO handle (ROWID, id, service) VALUES (2, 'friend@example.com', 'iMessage')")
    # Two chats: 1 = 1:1 (style 45), 2 = group (style 43)
    c.execute("INSERT INTO chat (ROWID, style) VALUES (1, 45)")
    c.execute("INSERT INTO chat (ROWID, style) VALUES (2, 43)")
    # Apple ns date: (unix - 978307200) * 1e9
    # Use ts=2_000_000_000 (year 2033) and ts=2_000_000_500 to ensure ordering
    base = (2_000_000_000 - 978_307_200) * 1_000_000_000
    c.execute("INSERT INTO message (text, handle_id, is_from_me, date) "
              "VALUES (?, 1, 0, ?)", ("hey", base))
    c.execute("INSERT INTO message (text, handle_id, is_from_me, date) "
              "VALUES (?, 2, 1, ?)", ("how are you", base + 500_000_000_000))
    c.execute("INSERT INTO chat_message_join (chat_id, message_id) VALUES (1, 1)")
    c.execute("INSERT INTO chat_message_join (chat_id, message_id) VALUES (2, 2)")
    c.execute("INSERT INTO chat_handle_join (chat_id, handle_id) VALUES (1, 1)")
    c.execute("INSERT INTO chat_handle_join (chat_id, handle_id) VALUES (2, 2)")
    c.commit()
    c.close()
    return p


# --- access status ---

def test_access_status_real_path():
    s = imessage.access_status()
    assert "exists" in s
    assert "readable" in s
    assert "path" in s


def test_no_access_returns_error_dict(tmp_path):
    """When chat.db doesn't exist, current_chat returns an error not a crash."""
    fake = tmp_path / "nonexistent.db"
    with patch.object(imessage, "CHAT_DB", fake):
        out = imessage.current_chat()
    assert "error" in out


# --- current_chat ---

def test_current_chat_returns_most_recent(fake_chat_db):
    with patch.object(imessage, "CHAT_DB", fake_chat_db):
        out = imessage.current_chat()
    assert out["handle"] == "friend@example.com"  # the later message
    assert out["service"] == "iMessage"
    assert out["last_text"] == "how are you"
    assert out["is_group"] is True  # we put friend in chat 2 (style 43)


def test_current_chat_includes_timestamp(fake_chat_db):
    with patch.object(imessage, "CHAT_DB", fake_chat_db):
        out = imessage.current_chat()
    # Should be approximately 2033 (we used 2_000_000_500)
    assert 1_900_000_000 < out["last_message_ts"] < 2_100_000_000


def test_current_chat_no_messages(tmp_path):
    """Empty chat.db returns an error rather than crashing."""
    p = tmp_path / "empty.db"
    c = sqlite3.connect(str(p))
    c.executescript("""
        CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT, service TEXT);
        CREATE TABLE chat (ROWID INTEGER PRIMARY KEY, style INTEGER);
        CREATE TABLE message (ROWID INTEGER PRIMARY KEY, text TEXT,
                              handle_id INTEGER, is_from_me INTEGER, date INTEGER);
        CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
        CREATE TABLE chat_handle_join (chat_id INTEGER, handle_id INTEGER);
    """)
    c.commit()
    c.close()
    with patch.object(imessage, "CHAT_DB", p):
        out = imessage.current_chat()
    assert "error" in out


# --- recent_chats ---

def test_recent_chats_returns_list(fake_chat_db):
    with patch.object(imessage, "CHAT_DB", fake_chat_db):
        chats = imessage.recent_chats()
    assert len(chats) == 2
    # Newest first
    assert chats[0]["handle"] == "friend@example.com"
    assert chats[1]["handle"] == "+15551234567"


def test_recent_chats_respects_limit(fake_chat_db):
    with patch.object(imessage, "CHAT_DB", fake_chat_db):
        chats = imessage.recent_chats(limit=1)
    assert len(chats) == 1


def test_recent_chats_no_access_returns_empty(tmp_path):
    fake = tmp_path / "nonexistent.db"
    with patch.object(imessage, "CHAT_DB", fake):
        assert imessage.recent_chats() == []


# --- recent_messages ---

def test_recent_messages_filters_by_handle(fake_chat_db):
    with patch.object(imessage, "CHAT_DB", fake_chat_db):
        msgs = imessage.recent_messages("friend@example.com")
    assert len(msgs) == 1
    assert msgs[0]["text"] == "how are you"
    assert msgs[0]["from_me"] is True


def test_recent_messages_other_handle(fake_chat_db):
    with patch.object(imessage, "CHAT_DB", fake_chat_db):
        msgs = imessage.recent_messages("+15551234567")
    assert len(msgs) == 1
    assert msgs[0]["from_me"] is False


def test_recent_messages_unknown_handle(fake_chat_db):
    with patch.object(imessage, "CHAT_DB", fake_chat_db):
        msgs = imessage.recent_messages("nobody@nowhere")
    assert msgs == []


def test_recent_messages_empty_handle_returns_empty():
    assert imessage.recent_messages("") == []


def test_recent_messages_no_access_returns_empty(tmp_path):
    fake = tmp_path / "nonexistent.db"
    with patch.object(imessage, "CHAT_DB", fake):
        assert imessage.recent_messages("anything") == []
