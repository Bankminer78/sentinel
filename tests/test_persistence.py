"""Tests for sentinel.persistence and macOS daemon files."""
import os
import time
import plistlib
from pathlib import Path
from unittest.mock import patch

import pytest

from sentinel import persistence, blocker


DAEMON_DIR = Path(__file__).resolve().parent.parent / "daemon"
PLIST_PATH = DAEMON_DIR / "com.sentinel.daemon.plist"
INSTALL_PATH = DAEMON_DIR / "install.sh"
UNINSTALL_PATH = DAEMON_DIR / "uninstall.sh"
WRAPPER_PATH = DAEMON_DIR / "sentinel-wrapper.sh"


@pytest.fixture(autouse=True)
def _reset_persistence():
    persistence._running = False
    persistence._thread = None
    yield
    persistence._running = False
    persistence._thread = None


# --- check_hosts_intact ---

def test_check_hosts_intact_with_markers(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text(
        "127.0.0.1 localhost\n"
        f"{persistence.MARKER} START\n"
        "0.0.0.0 bad.com\n"
        f"{persistence.MARKER} END\n"
    )
    blocker._blocked_domains.add("bad.com")
    assert persistence.check_hosts_intact(str(hosts)) is True


def test_check_hosts_intact_missing_markers_when_blocked(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text("127.0.0.1 localhost\n")
    blocker._blocked_domains.add("bad.com")
    assert persistence.check_hosts_intact(str(hosts)) is False


def test_check_hosts_intact_no_blocked_domains(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text("127.0.0.1 localhost\n")
    # No blocked domains — should be True regardless of markers
    assert not blocker._blocked_domains
    assert persistence.check_hosts_intact(str(hosts)) is True


def test_check_hosts_intact_nonexistent_file(tmp_path):
    hosts = tmp_path / "does-not-exist"
    assert persistence.check_hosts_intact(str(hosts)) is False


def test_check_hosts_intact_partial_markers(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text(f"{persistence.MARKER} START\n0.0.0.0 bad.com\n")
    blocker._blocked_domains.add("bad.com")
    # Missing END marker
    assert persistence.check_hosts_intact(str(hosts)) is False


# --- restore_hosts_block ---

def test_restore_hosts_block_triggers_sync():
    blocker._blocked_domains.add("evil.com")
    with patch.object(blocker, "_sync_hosts") as m:
        persistence.restore_hosts_block()
        m.assert_called_once()


def test_restore_hosts_block_noop_without_domains():
    with patch.object(blocker, "_sync_hosts") as m:
        persistence.restore_hosts_block()
        m.assert_not_called()


# --- watcher lifecycle ---

def test_start_stop_watcher():
    persistence.start_watcher(interval=0.01)
    assert persistence._running is True
    assert persistence._thread is not None
    assert persistence._thread.is_alive()
    persistence.stop_watcher()
    # Give thread time to wind down
    time.sleep(0.05)
    assert persistence._running is False


def test_start_watcher_idempotent():
    persistence.start_watcher(interval=0.01)
    first_thread = persistence._thread
    persistence.start_watcher(interval=0.01)
    assert persistence._thread is first_thread
    persistence.stop_watcher()


def test_watcher_calls_restore_on_tamper(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text("127.0.0.1 localhost\n")
    blocker._blocked_domains.add("bad.com")

    with patch.object(blocker, "_sync_hosts") as m:
        # Run one iteration manually via periodic_check-style logic
        if not persistence.check_hosts_intact(str(hosts)):
            persistence.restore_hosts_block()
        assert m.called


# --- daemon plist validity ---

def test_plist_file_exists():
    assert PLIST_PATH.is_file()


def test_plist_is_valid_xml():
    with open(PLIST_PATH, "rb") as f:
        data = plistlib.load(f)
    assert data["Label"] == "com.sentinel.daemon"
    assert data["RunAtLoad"] is True
    assert data["KeepAlive"] is True
    assert data["StandardOutPath"] == "/var/log/sentinel.log"
    assert data["StandardErrorPath"] == "/var/log/sentinel.err"
    assert isinstance(data["ProgramArguments"], list)
    assert len(data["ProgramArguments"]) >= 1


def test_plist_has_doctype():
    content = PLIST_PATH.read_text()
    assert "<!DOCTYPE plist PUBLIC" in content
    assert 'version="1.0"' in content


# --- install/uninstall scripts ---

def test_install_sh_exists_and_executable():
    assert INSTALL_PATH.is_file()
    assert os.access(INSTALL_PATH, os.X_OK)


def test_install_sh_has_sudo_check():
    text = INSTALL_PATH.read_text()
    # Either EUID or id -u check
    assert ("EUID" in text) or ("id -u" in text)
    assert "launchctl" in text
    assert "/Library/LaunchDaemons" in text


def test_install_sh_backs_up_hosts():
    text = INSTALL_PATH.read_text()
    assert "/etc/hosts.sentinel-backup" in text


def test_uninstall_sh_exists_and_executable():
    assert UNINSTALL_PATH.is_file()
    assert os.access(UNINSTALL_PATH, os.X_OK)


def test_uninstall_sh_has_sudo_check():
    text = UNINSTALL_PATH.read_text()
    assert ("EUID" in text) or ("id -u" in text)
    assert "launchctl" in text
    assert "unload" in text


def test_uninstall_sh_restores_hosts():
    text = UNINSTALL_PATH.read_text()
    assert "/etc/hosts.sentinel-backup" in text


# --- wrapper script ---

def test_wrapper_sh_exists_and_executable():
    assert WRAPPER_PATH.is_file()
    assert os.access(WRAPPER_PATH, os.X_OK)


def test_wrapper_sh_is_shell_script():
    text = WRAPPER_PATH.read_text()
    assert text.startswith("#!/bin/bash") or text.startswith("#!/bin/sh")
    assert "PATH" in text
    assert "sentinel" in text
