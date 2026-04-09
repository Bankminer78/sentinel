"""Tests for sentinel.applescript."""
import pytest
from unittest.mock import patch, MagicMock
from sentinel import applescript as asc


def test_run_applescript():
    with patch("sentinel.applescript.subprocess.run",
               return_value=MagicMock(returncode=0, stdout="result")):
        assert asc.run_applescript("return 1") == "result"


def test_run_applescript_error():
    with patch("sentinel.applescript.subprocess.run", side_effect=Exception("fail")):
        assert asc.run_applescript("bad") == ""


def test_display_dialog():
    with patch("sentinel.applescript.run_applescript", return_value="OK"):
        result = asc.display_dialog("Hello")
        assert result == "OK"


def test_get_user_input():
    with patch("sentinel.applescript.run_applescript", return_value="user input"):
        result = asc.get_user_input("Enter text")
        assert result == "user input"


def test_choose_from_list():
    with patch("sentinel.applescript.run_applescript", return_value="Option 1"):
        result = asc.choose_from_list(["Option 1", "Option 2"])
        assert result == "Option 1"


def test_applescript_api_snippet():
    snippet = asc.sentinel_applescript_api()
    assert "sentinelCall" in snippet
    assert "localhost:9849" in snippet


def test_run_automator_workflow():
    with patch("sentinel.applescript.subprocess.run",
               return_value=MagicMock(returncode=0, stdout="done")):
        result = asc.run_automator_workflow("/tmp/workflow.workflow")
        assert result == "done"


def test_activate_app():
    with patch("sentinel.applescript.run_applescript", return_value=""):
        assert asc.activate_app("Safari") is True


def test_get_running_apps():
    with patch("sentinel.applescript.run_applescript",
               return_value="Finder, Safari, Cursor"):
        apps = asc.get_running_apps()
        assert "Finder" in apps
        assert len(apps) == 3


def test_quit_app():
    with patch("sentinel.applescript.run_applescript", return_value=""):
        assert asc.quit_app("Chrome") is True
