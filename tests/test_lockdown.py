"""Tests for sentinel.lockdown — emergency lockdown mode."""

import time

import pytest

from sentinel import db, lockdown


class TestEnterLockdown:
    def test_returns_metadata(self, conn):
        info = lockdown.enter_lockdown(conn, 30)
        assert info["id"] >= 1
        assert info["duration_minutes"] == 30
        assert info["end_ts"] > info["start_ts"]

    def test_activates(self, conn):
        lockdown.enter_lockdown(conn, 10)
        assert lockdown.is_in_lockdown(conn) is True

    def test_with_password_hash(self, conn):
        info = lockdown.enter_lockdown(conn, 10, password_hash=lockdown._hash("secret"))
        assert info["id"] >= 1
        assert lockdown.is_in_lockdown(conn) is True

    def test_zero_duration_stores(self, conn):
        info = lockdown.enter_lockdown(conn, 0)
        assert info["end_ts"] == info["start_ts"]


class TestIsInLockdown:
    def test_empty(self, conn):
        assert lockdown.is_in_lockdown(conn) is False

    def test_auto_expires_passwordless(self, conn):
        lockdown.enter_lockdown(conn, 0)
        # already expired
        assert lockdown.is_in_lockdown(conn) is False

    def test_password_lock_does_not_auto_expire(self, conn):
        lockdown.enter_lockdown(conn, 0, password_hash=lockdown._hash("x"))
        assert lockdown.is_in_lockdown(conn) is True


class TestLockdownEnd:
    def test_returns_none_when_empty(self, conn):
        assert lockdown.get_lockdown_end(conn) is None

    def test_returns_end_ts(self, conn):
        info = lockdown.enter_lockdown(conn, 60)
        assert lockdown.get_lockdown_end(conn) == info["end_ts"]


class TestTryExit:
    def test_exit_when_no_lockdown(self, conn):
        assert lockdown.try_exit_lockdown(conn) is True

    def test_cannot_exit_before_expiry_passwordless(self, conn):
        lockdown.enter_lockdown(conn, 60)
        assert lockdown.try_exit_lockdown(conn) is False
        assert lockdown.is_in_lockdown(conn) is True

    def test_can_exit_after_expiry_passwordless(self, conn):
        lockdown.enter_lockdown(conn, 0)
        # auto-expires
        assert lockdown.try_exit_lockdown(conn) is True

    def test_password_correct_exits(self, conn):
        lockdown.enter_lockdown(conn, 60, password_hash=lockdown._hash("pw"))
        assert lockdown.try_exit_lockdown(conn, "pw") is True
        assert lockdown.is_in_lockdown(conn) is False

    def test_password_wrong_blocks(self, conn):
        lockdown.enter_lockdown(conn, 60, password_hash=lockdown._hash("pw"))
        assert lockdown.try_exit_lockdown(conn, "bad") is False
        assert lockdown.is_in_lockdown(conn) is True

    def test_password_none_blocks_when_set(self, conn):
        lockdown.enter_lockdown(conn, 60, password_hash=lockdown._hash("pw"))
        assert lockdown.try_exit_lockdown(conn, None) is False


class TestExtend:
    def test_extend_pushes_end(self, conn):
        info = lockdown.enter_lockdown(conn, 10)
        orig_end = info["end_ts"]
        lockdown.extend_lockdown(conn, 5)
        new_end = lockdown.get_lockdown_end(conn)
        assert new_end == pytest.approx(orig_end + 300, abs=1)

    def test_extend_no_active_noop(self, conn):
        lockdown.extend_lockdown(conn, 10)  # should not raise
        assert lockdown.is_in_lockdown(conn) is False


class TestEmergencyContact:
    def test_default_empty(self, conn):
        assert lockdown.emergency_contact(conn) == ""

    def test_reads_from_config(self, conn):
        db.set_config(conn, "emergency_contact", "555-HELP")
        assert lockdown.emergency_contact(conn) == "555-HELP"
