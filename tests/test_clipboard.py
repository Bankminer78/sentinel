"""Tests for sentinel.clipboard."""
import pytest
from unittest.mock import patch, MagicMock
from sentinel import clipboard, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_get_clipboard_mock():
    with patch("sentinel.clipboard.subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0, stdout="hello world")
        assert clipboard.get_clipboard() == "hello world"


def test_get_clipboard_error():
    with patch("sentinel.clipboard.subprocess.run", side_effect=Exception("fail")):
        assert clipboard.get_clipboard() == ""


def test_set_clipboard():
    with patch("sentinel.clipboard.subprocess.run", return_value=MagicMock(returncode=0)):
        assert clipboard.set_clipboard("test") is True


def test_log_clipboard_empty(conn):
    with patch("sentinel.clipboard.get_clipboard", return_value=""):
        result = clipboard.log_clipboard(conn)
        assert result == 0


def test_log_clipboard_content(conn):
    with patch("sentinel.clipboard.get_clipboard", return_value="some text"):
        cid = clipboard.log_clipboard(conn, redact=False)
        assert cid > 0


def test_log_clipboard_redacts_pii(conn):
    with patch("sentinel.clipboard.get_clipboard", return_value="email me at test@example.com"):
        clipboard.log_clipboard(conn, redact=True)
        history = clipboard.get_history(conn)
        assert "[EMAIL]" in history[0]["content"]
        assert "test@example.com" not in history[0]["content"]


def test_get_history_empty(conn):
    assert clipboard.get_history(conn) == []


def test_clear_history(conn):
    with patch("sentinel.clipboard.get_clipboard", return_value="data"):
        clipboard.log_clipboard(conn)
    clipboard.clear_history(conn)
    assert clipboard.get_history(conn) == []


def test_search_history(conn):
    with patch("sentinel.clipboard.get_clipboard", return_value="hello world"):
        clipboard.log_clipboard(conn, redact=False)
    results = clipboard.search_history(conn, "hello")
    assert len(results) == 1


def test_purge_old(conn):
    with patch("sentinel.clipboard.get_clipboard", return_value="data"):
        clipboard.log_clipboard(conn)
    # Backdate the entry
    import time
    conn.execute("UPDATE clipboard_history SET ts=?", (time.time() - 100 * 86400,))
    conn.commit()
    count = clipboard.purge_old(conn, days=7)
    assert count >= 1
