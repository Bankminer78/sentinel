"""Tests for sentinel.hotkeys."""
import pytest
from sentinel import hotkeys, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_list_hotkeys(conn):
    keys = hotkeys.list_hotkeys(conn)
    assert len(keys) >= 5


def test_get_hotkey_default(conn):
    key = hotkeys.get_hotkey(conn, "quick_add_rule")
    assert "cmd" in key


def test_get_nonexistent_hotkey(conn):
    assert hotkeys.get_hotkey(conn, "nonexistent") == ""


def test_set_hotkey(conn):
    assert hotkeys.set_hotkey(conn, "quick_add_rule", "cmd+n") is True
    assert hotkeys.get_hotkey(conn, "quick_add_rule") == "cmd+n"


def test_set_invalid_action(conn):
    assert hotkeys.set_hotkey(conn, "nonexistent", "cmd+x") is False


def test_reset_hotkey(conn):
    hotkeys.set_hotkey(conn, "quick_add_rule", "cmd+n")
    hotkeys.reset_hotkey(conn, "quick_add_rule")
    default = hotkeys.DEFAULT_HOTKEYS["quick_add_rule"]["keys"]
    assert hotkeys.get_hotkey(conn, "quick_add_rule") == default


def test_reset_all(conn):
    hotkeys.set_hotkey(conn, "quick_add_rule", "cmd+n")
    hotkeys.reset_all(conn)
    default = hotkeys.DEFAULT_HOTKEYS["quick_add_rule"]["keys"]
    assert hotkeys.get_hotkey(conn, "quick_add_rule") == default


def test_available_actions():
    actions = hotkeys.available_actions()
    assert "quick_add_rule" in actions
    assert "start_pomodoro" in actions


def test_validate_hotkey_valid():
    assert hotkeys.validate_hotkey("cmd+shift+r") is True
    assert hotkeys.validate_hotkey("ctrl+a") is True


def test_validate_hotkey_invalid():
    assert hotkeys.validate_hotkey("") is False
    assert hotkeys.validate_hotkey("just_text") is False


def test_count_hotkeys():
    assert hotkeys.count_hotkeys() >= 5


def test_export_hotkeys(conn):
    import json
    exported = hotkeys.export_hotkeys(conn)
    data = json.loads(exported)
    assert len(data) >= 5
