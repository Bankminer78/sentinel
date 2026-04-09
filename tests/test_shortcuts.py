"""Tests for sentinel.shortcuts."""
import pytest
from unittest.mock import patch, MagicMock
from sentinel import shortcuts


def test_list_actions():
    actions = shortcuts.list_available_actions()
    assert len(actions) > 0
    assert "start_focus" in actions


def test_generate_shortcut_url():
    url = shortcuts.generate_shortcut_url("start_focus", {"minutes": 30})
    assert url.startswith("sentinel://")
    assert "minutes=30" in url


def test_generate_shortcut_url_no_params():
    url = shortcuts.generate_shortcut_url("check_score")
    assert url == "sentinel://check_score"


def test_list_installed_shortcuts():
    with patch("sentinel.shortcuts.subprocess.run",
               return_value=MagicMock(returncode=0, stdout="Morning\nEvening")):
        result = shortcuts.list_installed_shortcuts()
        assert len(result) == 2


def test_list_installed_error():
    with patch("sentinel.shortcuts.subprocess.run", side_effect=Exception("fail")):
        assert shortcuts.list_installed_shortcuts() == []


def test_run_shortcut():
    with patch("sentinel.shortcuts.subprocess.run",
               return_value=MagicMock(returncode=0, stdout="result")):
        result = shortcuts.run_shortcut("MyShortcut")
        assert result == "result"


def test_run_shortcut_error():
    with patch("sentinel.shortcuts.subprocess.run", side_effect=Exception("fail")):
        assert shortcuts.run_shortcut("X") == ""


def test_export_definitions():
    defs = shortcuts.export_shortcut_definitions()
    assert "actions" in defs
    assert len(defs["actions"]) > 0


def test_is_shortcuts_available():
    with patch("sentinel.shortcuts.subprocess.run",
               return_value=MagicMock(returncode=0)):
        assert shortcuts.is_shortcuts_available() is True


def test_is_shortcuts_unavailable():
    with patch("sentinel.shortcuts.subprocess.run",
               return_value=MagicMock(returncode=1)):
        assert shortcuts.is_shortcuts_available() is False
