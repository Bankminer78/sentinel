"""Tests for sentinel.browser_history."""
import pytest
from unittest.mock import patch, MagicMock
from sentinel import browser_history, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_extract_domain():
    assert browser_history._extract_domain("https://www.youtube.com/watch") == "youtube.com"
    assert browser_history._extract_domain("http://github.com") == "github.com"
    assert browser_history._extract_domain("") == ""
    assert browser_history._extract_domain("invalid") == "invalid"


def test_top_domains_empty():
    assert browser_history.top_domains([]) == []


def test_top_domains_basic():
    history = [
        {"url": "https://youtube.com/watch?v=1", "visit_count": 5},
        {"url": "https://github.com/repo", "visit_count": 10},
        {"url": "https://youtube.com/watch?v=2", "visit_count": 3},
    ]
    top = browser_history.top_domains(history)
    assert top[0]["domain"] == "github.com"
    assert top[0]["visits"] == 10
    assert top[1]["domain"] == "youtube.com"
    assert top[1]["visits"] == 8  # 5 + 3


def test_top_domains_limit():
    history = [{"url": f"https://site{i}.com", "visit_count": i} for i in range(100)]
    top = browser_history.top_domains(history, limit=5)
    assert len(top) == 5


def test_read_nonexistent_chrome():
    with patch.object(browser_history, "CHROME_HISTORY",
                      Path("/nonexistent/path")):
        result = browser_history.read_chrome_history()
        assert result == []


def test_read_nonexistent_arc():
    with patch.object(browser_history, "ARC_HISTORY",
                      Path("/nonexistent/path")):
        result = browser_history.read_arc_history()
        assert result == []


def test_read_nonexistent_safari():
    with patch.object(browser_history, "SAFARI_HISTORY",
                      Path("/nonexistent/path")):
        result = browser_history.read_safari_history()
        assert result == []


def test_bootstrap_invalid_source(conn):
    count = browser_history.bootstrap_skiplist_from_history(conn, "invalid")
    assert count == 0


def test_bootstrap_chrome(conn):
    mock_history = [
        {"url": "https://github.com", "visit_count": 50},
        {"url": "https://example.com", "visit_count": 20},
    ]
    with patch.object(browser_history, "read_chrome_history", return_value=mock_history):
        count = browser_history.bootstrap_skiplist_from_history(conn, "chrome")
        assert count == 2
        # Verify saved
        assert db.get_seen(conn, "github.com") == "none"
        assert db.get_seen(conn, "example.com") == "none"


def test_bootstrap_skip_already_seen(conn):
    db.save_seen(conn, "github.com", "none")
    mock_history = [{"url": "https://github.com", "visit_count": 10}]
    with patch.object(browser_history, "read_chrome_history", return_value=mock_history):
        count = browser_history.bootstrap_skiplist_from_history(conn, "chrome")
        assert count == 0  # Already seen


def test_top_domains_ignores_empty_urls():
    history = [{"url": "", "visit_count": 1}, {"url": "https://github.com", "visit_count": 1}]
    top = browser_history.top_domains(history)
    assert len(top) == 1
    assert top[0]["domain"] == "github.com"
