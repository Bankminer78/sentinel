"""Tests for sentinel.email_notif."""
import json
import pytest
from unittest.mock import patch, MagicMock
from sentinel import email_notif, db


def test_configure_email(conn):
    email_notif.configure_email(conn, "smtp.test.com", 587, "u", "p", "f@t.com")
    cfg = email_notif.get_email_config(conn)
    assert cfg["smtp_host"] == "smtp.test.com"
    assert cfg["smtp_port"] == 587
    assert cfg["username"] == "u"
    assert cfg["from_addr"] == "f@t.com"


def test_get_email_config_empty(conn):
    assert email_notif.get_email_config(conn) == {}


def test_get_email_config_stores_json(conn):
    email_notif.configure_email(conn, "h", 25, "u", "p", "f")
    raw = db.get_config(conn, "email_config")
    assert json.loads(raw)["smtp_host"] == "h"


def test_send_email_no_config(conn):
    assert email_notif.send_email(conn, "to@t.com", "s", "b") is False


def test_send_email_success(conn):
    email_notif.configure_email(conn, "smtp.test.com", 587, "u", "p", "f@t.com")
    with patch("sentinel.email_notif.smtplib.SMTP") as mock_smtp:
        server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = server
        assert email_notif.send_email(conn, "to@t.com", "sub", "body") is True
        server.login.assert_called_once_with("u", "p")
        server.send_message.assert_called_once()


def test_send_email_html(conn):
    email_notif.configure_email(conn, "smtp.test.com", 587, "u", "p", "f@t.com")
    with patch("sentinel.email_notif.smtplib.SMTP") as mock_smtp:
        server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = server
        assert email_notif.send_email(conn, "to@t.com", "s", "<p>x</p>", html=True) is True


def test_send_email_exception(conn):
    email_notif.configure_email(conn, "smtp.test.com", 587, "u", "p", "f@t.com")
    with patch("sentinel.email_notif.smtplib.SMTP", side_effect=Exception("boom")):
        assert email_notif.send_email(conn, "to@t.com", "s", "b") is False


def test_send_digest_email(conn):
    email_notif.configure_email(conn, "smtp.test.com", 587, "u", "p", "f@t.com")
    with patch("sentinel.email_notif.send_email", return_value=True) as mock:
        assert email_notif.send_digest_email(conn, "to@t.com", "digest") is True
        mock.assert_called_once()
        assert mock.call_args[0][2] == "Sentinel Daily Digest"


def test_test_email_config_no_config(conn):
    assert email_notif.test_email_config(conn) is False


def test_test_email_config_success(conn):
    email_notif.configure_email(conn, "smtp.test.com", 587, "u", "p", "f@t.com")
    with patch("sentinel.email_notif.smtplib.SMTP") as mock_smtp:
        server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = server
        assert email_notif.test_email_config(conn) is True


def test_test_email_config_failure(conn):
    email_notif.configure_email(conn, "smtp.test.com", 587, "u", "p", "f@t.com")
    with patch("sentinel.email_notif.smtplib.SMTP", side_effect=Exception("x")):
        assert email_notif.test_email_config(conn) is False


@pytest.mark.asyncio
async def test_send_email_async(conn):
    email_notif.configure_email(conn, "smtp.test.com", 587, "u", "p", "f@t.com")
    with patch("sentinel.email_notif.send_email", return_value=True):
        ok = await email_notif.send_email_async(conn, "to@t.com", "s", "b")
        assert ok is True


def test_build_message_plain():
    msg = email_notif._build_message(
        {"from_addr": "f@t.com"}, "to@t.com", "sub", "body", False)
    assert msg["To"] == "to@t.com"
    assert msg["From"] == "f@t.com"
    assert msg["Subject"] == "sub"


def test_build_message_html_has_alternative():
    msg = email_notif._build_message(
        {"from_addr": "f@t.com"}, "to@t.com", "sub", "<p>x</p>", True)
    assert msg.is_multipart()
