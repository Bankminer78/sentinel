"""Tests for sentinel.notification_center."""
import pytest
from unittest.mock import patch, MagicMock
from sentinel import notification_center as nc


def test_send_banner():
    with patch("sentinel.notification_center.subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0)
        assert nc.send_banner("Title", "Message") is True


def test_send_banner_with_sound():
    with patch("sentinel.notification_center.subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0)
        nc.send_banner("T", "M", sound="Glass")
        args = mock.call_args[0][0]
        assert any("Glass" in a for a in args)


def test_send_alert():
    with patch("sentinel.notification_center.subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0)
        assert nc.send_alert("Title", "Message") is True


def test_send_with_actions():
    with patch("sentinel.notification_center.subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0)
        assert nc.send_with_actions("T", "M", ["OK", "Cancel"]) is True


def test_badge_count_unsupported():
    # macOS limitation
    assert nc.badge_count("SomeApp", 5) is False


def test_clear_notifications():
    with patch("sentinel.notification_center.subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0)
        assert nc.clear_notifications() is True


def test_send_progress():
    with patch("sentinel.notification_center.subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0)
        result = nc.send_progress("Task", 0.5)
        assert result is True


def test_group_notifications_empty():
    assert nc.group_notifications("test", []) is True


def test_group_notifications_with_items():
    with patch("sentinel.notification_center.subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0)
        assert nc.group_notifications("test", ["item1", "item2"]) is True


def test_escape_quotes():
    result = nc._escape('Hello "world"')
    assert '\\"' in result


def test_send_banner_error():
    with patch("sentinel.notification_center.subprocess.run", side_effect=Exception("fail")):
        assert nc.send_banner("T", "M") is False
