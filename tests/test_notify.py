"""Tests for sentinel.notify — osascript notify + dialog effectors.

Tests mock subprocess so they don't actually fire macOS popups.
"""
from unittest.mock import patch, MagicMock
import subprocess
import pytest

from sentinel import notify


# --- notify ---

def test_notify_calls_osascript():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr=b"")
        out = notify.notify("Title", "Body")
    assert out["ok"] is True
    args, kwargs = mock_run.call_args
    cmd = args[0]
    assert cmd[0] == "osascript"
    # The script should contain the title and body
    script = cmd[2]
    assert "Title" in script
    assert "Body" in script
    assert "display notification" in script


def test_notify_with_subtitle():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr=b"")
        notify.notify("T", "B", subtitle="Sub")
    script = mock_run.call_args[0][0][2]
    assert "subtitle" in script
    assert "Sub" in script


def test_notify_escapes_quotes():
    """A title containing a double-quote must not break the AppleScript."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr=b"")
        notify.notify('Sneaky "title"', 'Body with "quote"')
    script = mock_run.call_args[0][0][2]
    # Quotes should be escaped (AppleScript uses \" inside string literals)
    assert '\\"title\\"' in script
    assert '\\"quote\\"' in script


def test_notify_escapes_backslashes():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr=b"")
        notify.notify("path\\to\\file", "")
    script = mock_run.call_args[0][0][2]
    assert "path\\\\to\\\\file" in script


def test_notify_handles_failure():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr=b"oops")
        out = notify.notify("T", "B")
    assert out["ok"] is False
    assert "oops" in (out.get("stderr") or "")


def test_notify_handles_missing_osascript():
    with patch("subprocess.run", side_effect=FileNotFoundError("no osascript")):
        out = notify.notify("T", "B")
    assert out["ok"] is False
    assert "error" in out


def test_notify_default_title():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr=b"")
        notify.notify("", "")
    script = mock_run.call_args[0][0][2]
    assert "Sentinel" in script  # default


# --- dialog ---

def test_dialog_basic():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="button returned:OK", stderr="")
        out = notify.dialog("Title", "Body")
    assert out["ok"] is True
    assert out["button"] == "OK"


def test_dialog_with_custom_buttons():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="button returned:Yes", stderr="")
        out = notify.dialog("T", "B", buttons=["Yes", "No"])
    script = mock_run.call_args[0][0][2]
    assert '"Yes"' in script
    assert '"No"' in script
    assert out["button"] == "Yes"


def test_dialog_default_button():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="button returned:OK", stderr="")
        notify.dialog("T", "B", buttons=["OK", "Cancel"], default_button="OK")
    script = mock_run.call_args[0][0][2]
    assert 'default button "OK"' in script


def test_dialog_timeout():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="button returned:OK, gave up:false", stderr="")
        notify.dialog("T", "B", timeout_seconds=10)
    script = mock_run.call_args[0][0][2]
    assert "giving up after 10" in script


def test_dialog_timeout_returns_error():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="button returned:OK, gave up:true", stderr="")
        out = notify.dialog("T", "B", timeout_seconds=10)
    assert out["ok"] is False
    assert out["error"] == "timeout"


def test_dialog_user_cancelled():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="execution error: User canceled")
        out = notify.dialog("T", "B")
    assert out["ok"] is False


def test_dialog_subprocess_timeout():
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("osa", 5)):
        out = notify.dialog("T", "B")
    assert out["ok"] is False
    assert out["error"] == "timeout"


def test_dialog_escapes_quotes():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="button returned:OK", stderr="")
        notify.dialog('"injection"', '"more"')
    script = mock_run.call_args[0][0][2]
    assert '\\"injection\\"' in script
