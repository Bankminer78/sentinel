"""Tests for sentinel.blocker — Block enforcer (module-level state)."""

from unittest.mock import patch, MagicMock

import pytest

from sentinel import blocker


# ---------------------------------------------------------------------------
# block_domain / unblock_domain
# ---------------------------------------------------------------------------


class TestBlockDomain:
    """Tests for domain blocking."""

    def test_block_domain_adds_to_set(self):
        with patch.object(blocker, "_sync_hosts"):
            blocker.block_domain("twitter.com")
            assert "twitter.com" in blocker._blocked_domains

    def test_block_domain_calls_sync_hosts(self):
        with patch.object(blocker, "_sync_hosts") as mock_sync:
            blocker.block_domain("twitter.com")
            mock_sync.assert_called_once()

    def test_block_multiple_domains(self):
        with patch.object(blocker, "_sync_hosts"):
            blocker.block_domain("twitter.com")
            blocker.block_domain("facebook.com")
            blocker.block_domain("reddit.com")
            assert "twitter.com" in blocker._blocked_domains
            assert "facebook.com" in blocker._blocked_domains
            assert "reddit.com" in blocker._blocked_domains

    def test_block_domain_idempotent(self):
        with patch.object(blocker, "_sync_hosts"):
            blocker.block_domain("twitter.com")
            blocker.block_domain("twitter.com")
            assert len([d for d in blocker._blocked_domains if d == "twitter.com"]) == 1

    def test_unblock_domain_removes_from_set(self):
        with patch.object(blocker, "_sync_hosts"):
            blocker.block_domain("twitter.com")
            blocker.unblock_domain("twitter.com")
            assert "twitter.com" not in blocker._blocked_domains

    def test_unblock_domain_calls_sync_hosts(self):
        with patch.object(blocker, "_sync_hosts"):
            blocker.block_domain("twitter.com")
        with patch.object(blocker, "_sync_hosts") as mock_sync:
            blocker.unblock_domain("twitter.com")
            mock_sync.assert_called_once()

    def test_unblock_nonexistent_domain_no_crash(self):
        with patch.object(blocker, "_sync_hosts"):
            blocker.unblock_domain("never-blocked.com")

    def test_unblock_preserves_other_blocks(self):
        with patch.object(blocker, "_sync_hosts"):
            blocker.block_domain("twitter.com")
            blocker.block_domain("facebook.com")
            blocker.unblock_domain("twitter.com")
            assert "twitter.com" not in blocker._blocked_domains
            assert "facebook.com" in blocker._blocked_domains

    def test_block_domain_with_subdomain(self):
        with patch.object(blocker, "_sync_hosts"):
            blocker.block_domain("www.twitter.com")
            assert "www.twitter.com" in blocker._blocked_domains


# ---------------------------------------------------------------------------
# block_app / unblock_app
# ---------------------------------------------------------------------------


class TestBlockApp:
    """Tests for app blocking."""

    def test_block_app_adds_to_set(self):
        with patch.object(blocker, "kill_app"):
            blocker.block_app("com.discord.Discord")
            assert "com.discord.Discord" in blocker._blocked_apps

    def test_block_app_calls_kill(self):
        with patch.object(blocker, "kill_app") as mock_kill:
            blocker.block_app("com.discord.Discord")
            mock_kill.assert_called_once_with("com.discord.Discord")

    def test_unblock_app_removes_from_set(self):
        with patch.object(blocker, "kill_app"):
            blocker.block_app("com.discord.Discord")
        blocker.unblock_app("com.discord.Discord")
        assert "com.discord.Discord" not in blocker._blocked_apps

    def test_unblock_app_nonexistent_no_crash(self):
        blocker.unblock_app("com.nonexistent.App")

    def test_block_multiple_apps(self):
        with patch.object(blocker, "kill_app"):
            blocker.block_app("com.discord.Discord")
            blocker.block_app("com.valvesoftware.Steam")
            assert "com.discord.Discord" in blocker._blocked_apps
            assert "com.valvesoftware.Steam" in blocker._blocked_apps


# ---------------------------------------------------------------------------
# kill_app
# ---------------------------------------------------------------------------


class TestKillApp:
    """Tests for force-terminating apps."""

    def test_kill_app_calls_osascript(self):
        with patch("sentinel.blocker.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="1234\n")
            blocker.kill_app("com.apple.Safari")
            assert mock_run.call_count == 2
            first_call_args = str(mock_run.call_args_list[0])
            assert "osascript" in first_call_args
            second_call_args = str(mock_run.call_args_list[1])
            assert "kill" in second_call_args

    def test_kill_app_uses_bundle_id_in_script(self):
        with patch("sentinel.blocker.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="5678\n")
            blocker.kill_app("com.google.Chrome")
            call_str = str(mock_run.call_args_list[0])
            assert "com.google.Chrome" in call_str

    def test_kill_app_nonexistent_no_crash(self):
        with patch("sentinel.blocker.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="No matching processes")
            blocker.kill_app("com.nonexistent.app")

    def test_kill_app_handles_exception(self):
        with patch("sentinel.blocker.subprocess.run", side_effect=Exception("OS error")):
            blocker.kill_app("com.test.app")  # Should not raise


# ---------------------------------------------------------------------------
# is_blocked_domain / is_blocked_app
# ---------------------------------------------------------------------------


class TestIsBlocked:
    """Tests for blocked status checks."""

    def test_is_blocked_domain_false_initially(self):
        assert blocker.is_blocked_domain("twitter.com") is False

    def test_is_blocked_domain_after_block(self):
        with patch.object(blocker, "_sync_hosts"):
            blocker.block_domain("twitter.com")
            assert blocker.is_blocked_domain("twitter.com") is True

    def test_is_blocked_domain_after_unblock(self):
        with patch.object(blocker, "_sync_hosts"):
            blocker.block_domain("twitter.com")
            blocker.unblock_domain("twitter.com")
            assert blocker.is_blocked_domain("twitter.com") is False

    def test_is_blocked_domain_unrelated(self):
        with patch.object(blocker, "_sync_hosts"):
            blocker.block_domain("twitter.com")
            assert blocker.is_blocked_domain("github.com") is False

    def test_is_blocked_app_false_initially(self):
        assert blocker.is_blocked_app("com.discord.Discord") is False

    def test_is_blocked_app_after_block(self):
        with patch.object(blocker, "kill_app"):
            blocker.block_app("com.discord.Discord")
            assert blocker.is_blocked_app("com.discord.Discord") is True

    def test_is_blocked_app_after_unblock(self):
        with patch.object(blocker, "kill_app"):
            blocker.block_app("com.discord.Discord")
        blocker.unblock_app("com.discord.Discord")
        assert blocker.is_blocked_app("com.discord.Discord") is False


# ---------------------------------------------------------------------------
# get_blocked
# ---------------------------------------------------------------------------


class TestGetBlocked:
    """Tests for listing all blocked domains/apps."""

    def test_get_blocked_initially_empty(self):
        result = blocker.get_blocked()
        assert result == {"domains": [], "apps": []}

    def test_get_blocked_returns_dict(self):
        result = blocker.get_blocked()
        assert isinstance(result, dict)
        assert "domains" in result
        assert "apps" in result

    def test_get_blocked_includes_domains(self):
        with patch.object(blocker, "_sync_hosts"):
            blocker.block_domain("twitter.com")
            blocker.block_domain("facebook.com")
        result = blocker.get_blocked()
        assert "twitter.com" in result["domains"]
        assert "facebook.com" in result["domains"]

    def test_get_blocked_includes_apps(self):
        with patch.object(blocker, "kill_app"):
            blocker.block_app("com.discord.Discord")
        result = blocker.get_blocked()
        assert "com.discord.Discord" in result["apps"]

    def test_get_blocked_after_unblock(self):
        with patch.object(blocker, "_sync_hosts"):
            blocker.block_domain("twitter.com")
            blocker.block_domain("facebook.com")
            blocker.unblock_domain("twitter.com")
        result = blocker.get_blocked()
        assert "twitter.com" not in result["domains"]
        assert "facebook.com" in result["domains"]


# ---------------------------------------------------------------------------
# enforce
# ---------------------------------------------------------------------------


class TestEnforce:
    """Tests for the enforce function."""

    def test_enforce_kills_blocked_app(self):
        with patch.object(blocker, "kill_app") as mock_kill:
            blocker._blocked_apps.add("com.discord.Discord")
            blocker.enforce("com.discord.Discord")
            mock_kill.assert_called_once_with("com.discord.Discord")

    def test_enforce_does_not_kill_non_blocked_app(self):
        with patch.object(blocker, "kill_app") as mock_kill:
            blocker.enforce("com.apple.Safari")
            mock_kill.assert_not_called()


# ---------------------------------------------------------------------------
# _sync_hosts
# ---------------------------------------------------------------------------


class TestSyncHosts:
    """Tests for /etc/hosts synchronization."""

    def test_sync_hosts_writes_blocked_domains(self, tmp_path):
        hosts_file = tmp_path / "hosts"
        hosts_file.write_text("# Default hosts\n127.0.0.1 localhost\n")
        blocker._blocked_domains.add("twitter.com")
        with patch.object(blocker, "HOSTS_PATH", str(hosts_file)), \
             patch("sentinel.blocker.subprocess.run"):
            blocker._sync_hosts()
        content = hosts_file.read_text()
        assert "0.0.0.0 twitter.com" in content
        assert "0.0.0.0 www.twitter.com" in content

    def test_sync_hosts_removes_old_sentinel_block(self, tmp_path):
        hosts_file = tmp_path / "hosts"
        hosts_file.write_text(
            "127.0.0.1 localhost\n"
            "# SENTINEL BLOCK START\n"
            "0.0.0.0 old.com\n"
            "# SENTINEL BLOCK END\n"
        )
        blocker._blocked_domains.add("new.com")
        with patch.object(blocker, "HOSTS_PATH", str(hosts_file)), \
             patch("sentinel.blocker.subprocess.run"):
            blocker._sync_hosts()
        content = hosts_file.read_text()
        assert "old.com" not in content
        assert "0.0.0.0 new.com" in content

    def test_sync_hosts_preserves_original_entries(self, tmp_path):
        hosts_file = tmp_path / "hosts"
        hosts_file.write_text("127.0.0.1 localhost\n::1 localhost\n")
        blocker._blocked_domains.add("twitter.com")
        with patch.object(blocker, "HOSTS_PATH", str(hosts_file)), \
             patch("sentinel.blocker.subprocess.run"):
            blocker._sync_hosts()
        content = hosts_file.read_text()
        assert "127.0.0.1 localhost" in content

    def test_sync_hosts_empty_blocked_set(self, tmp_path):
        hosts_file = tmp_path / "hosts"
        hosts_file.write_text("127.0.0.1 localhost\n")
        with patch.object(blocker, "HOSTS_PATH", str(hosts_file)), \
             patch("sentinel.blocker.subprocess.run"):
            blocker._sync_hosts()
        content = hosts_file.read_text()
        assert "SENTINEL BLOCK START" not in content
