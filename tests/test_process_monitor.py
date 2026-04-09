"""Tests for sentinel.process_monitor."""
import pytest
from unittest.mock import patch, MagicMock
from sentinel import process_monitor as pm, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_get_top_processes():
    mock_output = """  PID COMMAND       %CPU %MEM
  100 python         5.2  1.5
  200 chrome        3.1  8.4
"""
    with patch("sentinel.process_monitor.subprocess.run",
               return_value=MagicMock(returncode=0, stdout=mock_output)):
        procs = pm.get_top_processes()
        assert len(procs) == 2
        assert procs[0]["pid"] == 100
        assert procs[0]["command"] == "python"


def test_get_top_processes_error():
    with patch("sentinel.process_monitor.subprocess.run", side_effect=Exception("fail")):
        assert pm.get_top_processes() == []


def test_get_process_by_name():
    with patch("sentinel.process_monitor.subprocess.run",
               return_value=MagicMock(returncode=0, stdout="123\n456\n")):
        pids = pm.get_process_by_name("chrome")
        assert pids == [123, 456]


def test_is_process_running():
    with patch("sentinel.process_monitor.get_process_by_name", return_value=[123]):
        assert pm.is_process_running("test") is True


def test_is_process_not_running():
    with patch("sentinel.process_monitor.get_process_by_name", return_value=[]):
        assert pm.is_process_running("ghost") is False


def test_kill_process():
    with patch("sentinel.process_monitor.subprocess.run", return_value=MagicMock(returncode=0)):
        assert pm.kill_process(123) is True


def test_log_top_processes(conn):
    with patch("sentinel.process_monitor.get_top_processes",
               return_value=[{"pid": 1, "command": "a", "cpu": 50.0, "memory": 10.0}]):
        pm.log_top_processes(conn)
    log = pm.get_process_log(conn)
    assert len(log) == 1


def test_get_process_log_empty(conn):
    assert pm.get_process_log(conn) == []


def test_cpu_hogs_empty(conn):
    assert pm.cpu_hogs(conn) == []


def test_cpu_hogs_with_data(conn):
    with patch("sentinel.process_monitor.get_top_processes",
               return_value=[{"pid": 1, "command": "bad_app", "cpu": 80.0, "memory": 10.0}]):
        pm.log_top_processes(conn)
    hogs = pm.cpu_hogs(conn, threshold=50)
    assert len(hogs) == 1


def test_get_process_by_name_none():
    with patch("sentinel.process_monitor.subprocess.run", side_effect=Exception("fail")):
        assert pm.get_process_by_name("test") == []
