"""Tests for sentinel.health — diagnostic checks."""

import time
from unittest.mock import patch, MagicMock

import pytest

from sentinel import db, health


class TestApiKey:
    def test_missing(self, conn):
        assert health.check_api_key(conn) is False

    def test_set(self, conn):
        db.set_config(conn, "gemini_api_key", "abc")
        assert health.check_api_key(conn) is True

    def test_empty_string_is_missing(self, conn):
        db.set_config(conn, "gemini_api_key", "   ")
        assert health.check_api_key(conn) is False


class TestDatabase:
    def test_healthy(self, conn):
        assert health.check_database(conn) is True

    def test_closed_unhealthy(self, conn):
        conn.close()
        assert health.check_database(conn) is False


class TestHostsAccess:
    def test_no_access_when_not_writable(self):
        with patch("sentinel.health.os.access", return_value=False):
            assert health.check_hosts_access() is False

    def test_access_when_writable(self):
        with patch("sentinel.health.os.access", return_value=True):
            assert health.check_hosts_access() is True


class TestDaemon:
    def test_running(self):
        fake = MagicMock(stdout="12345\t0\tcom.sentinel.daemon\n")
        with patch("sentinel.health.subprocess.run", return_value=fake):
            assert health.check_daemon_running() is True

    def test_not_running(self):
        fake = MagicMock(stdout="other.stuff\n")
        with patch("sentinel.health.subprocess.run", return_value=fake):
            assert health.check_daemon_running() is False

    def test_launchctl_error(self):
        with patch("sentinel.health.subprocess.run", side_effect=FileNotFoundError):
            assert health.check_daemon_running() is False


class TestBrowserExtension:
    def test_no_activity(self, conn):
        assert health.check_browser_extension(conn) is False

    def test_recent_activity(self, conn):
        db.log_activity(conn, "Chrome", "hi", "https://x.com/a", "x.com")
        assert health.check_browser_extension(conn) is True

    def test_old_activity_excluded(self, conn):
        conn.execute(
            "INSERT INTO activity_log (ts,app,title,url,domain) VALUES (?,?,?,?,?)",
            (time.time() - 99999, "", "", "https://x.com", "x.com"))
        conn.commit()
        assert health.check_browser_extension(conn) is False


class TestUptime:
    def test_uptime_positive(self):
        assert health.get_uptime() >= 0


class TestCheckHealth:
    def test_returns_all_fields(self, conn):
        with patch("sentinel.health.check_hosts_access", return_value=False), \
             patch("sentinel.health.check_daemon_running", return_value=False):
            out = health.check_health(conn)
        for k in ["api_key_set", "database_healthy", "hosts_writable",
                  "daemon_running", "browser_extension_connected",
                  "rules_count", "uptime_seconds", "issues"]:
            assert k in out

    def test_issues_reported(self, conn):
        with patch("sentinel.health.check_hosts_access", return_value=False), \
             patch("sentinel.health.check_daemon_running", return_value=False):
            out = health.check_health(conn)
        assert isinstance(out["issues"], list)
        assert len(out["issues"]) > 0

    def test_healthy_system_no_issues(self, conn):
        db.set_config(conn, "gemini_api_key", "key")
        db.add_rule(conn, "block social")
        db.log_activity(conn, "Chrome", "t", "https://x.com/a", "x.com")
        with patch("sentinel.health.check_hosts_access", return_value=True), \
             patch("sentinel.health.check_daemon_running", return_value=True):
            out = health.check_health(conn)
        assert out["api_key_set"] is True
        assert out["rules_count"] == 1
        assert out["issues"] == []

    def test_rules_count(self, conn):
        db.add_rule(conn, "r1")
        db.add_rule(conn, "r2")
        with patch("sentinel.health.check_hosts_access", return_value=True), \
             patch("sentinel.health.check_daemon_running", return_value=True):
            out = health.check_health(conn)
        assert out["rules_count"] == 2
