"""Tests for sentinel.dnd."""
import pytest
from unittest.mock import patch, MagicMock
from sentinel import dnd, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_enable_dnd():
    with patch("sentinel.dnd.subprocess.run", return_value=MagicMock(returncode=0)):
        assert dnd.enable_dnd() is True


def test_disable_dnd():
    with patch("sentinel.dnd.subprocess.run", return_value=MagicMock(returncode=0)):
        assert dnd.disable_dnd() is True


def test_enable_failure():
    with patch("sentinel.dnd.subprocess.run", side_effect=Exception("fail")):
        assert dnd.enable_dnd() is False


def test_log_dnd(conn):
    dnd.log_dnd(conn, "start")
    # Verify no error


def test_start_dnd_session(conn):
    with patch("sentinel.dnd.subprocess.run", return_value=MagicMock(returncode=0)):
        session = dnd.start_dnd_session(conn, 60)
        assert "started" in session
        assert "ends" in session


def test_end_dnd_session(conn):
    with patch("sentinel.dnd.subprocess.run", return_value=MagicMock(returncode=0)):
        dnd.end_dnd_session(conn)


def test_get_dnd_stats_empty(conn):
    stats = dnd.get_dnd_stats(conn)
    assert stats["sessions"] == 0


def test_get_dnd_stats_with_data(conn):
    with patch("sentinel.dnd.subprocess.run", return_value=MagicMock(returncode=0)):
        dnd.start_dnd_session(conn)
    stats = dnd.get_dnd_stats(conn)
    assert stats["sessions"] >= 1


def test_is_dnd_active():
    with patch("sentinel.dnd.subprocess.run",
               return_value=MagicMock(returncode=0, stdout="enabled = 1")):
        assert dnd.is_dnd_active() is True


def test_is_dnd_inactive():
    with patch("sentinel.dnd.subprocess.run",
               return_value=MagicMock(returncode=0, stdout="enabled = 0")):
        assert dnd.is_dnd_active() is False
