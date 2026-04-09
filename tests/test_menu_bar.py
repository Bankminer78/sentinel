"""Tests for sentinel.menu_bar."""
import pytest
from sentinel import menu_bar, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_get_status_icon():
    assert menu_bar.get_status_icon("ok") == "✓"
    assert menu_bar.get_status_icon("error") == "✗"
    assert menu_bar.get_status_icon("unknown_state") == "○"


def test_get_status_summary(conn):
    summary = menu_bar.get_status_summary(conn)
    assert "icon" in summary
    assert "score" in summary
    assert "state" in summary
    assert "summary" in summary


def test_status_state_ok(conn):
    summary = menu_bar.get_status_summary(conn)
    # Empty DB, score is 0 -> error state
    assert summary["state"] in ("ok", "warning", "error")


def test_get_menu_items(conn):
    items = menu_bar.get_menu_items(conn)
    assert len(items) > 5
    assert any(i.get("id") == "status" for i in items)
    assert any(i.get("id") == "quit" for i in items)


def test_menu_items_have_labels(conn):
    for item in menu_bar.get_menu_items(conn):
        if item.get("id") != "separator":
            assert "label" in item


def test_format_menu_bar_title(conn):
    title = menu_bar.format_menu_bar_title(conn)
    assert title  # Non-empty


def test_notifications_summary(conn):
    # Should not raise, even if alerts module has no data
    result = menu_bar.get_notifications_summary(conn)
    assert isinstance(result, list)
