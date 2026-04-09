"""Tests for sentinel.code_stats."""
import pytest
from unittest.mock import patch, MagicMock
from sentinel import code_stats as cs, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_get_commits_today_error():
    with patch("sentinel.code_stats.subprocess.run", side_effect=Exception("fail")):
        assert cs.get_commits_today() == []


def test_get_commits_today():
    mock_output = "abc|Fix bug|2026-04-09|Alice\ndef|Add feature|2026-04-09|Bob"
    with patch("sentinel.code_stats.subprocess.run",
               return_value=MagicMock(returncode=0, stdout=mock_output)):
        commits = cs.get_commits_today()
        assert len(commits) == 2
        assert commits[0]["hash"] == "abc"


def test_count_commits():
    with patch("sentinel.code_stats.subprocess.run",
               return_value=MagicMock(returncode=0, stdout="42")):
        assert cs.count_commits() == 42


def test_count_commits_error():
    with patch("sentinel.code_stats.subprocess.run", side_effect=Exception("fail")):
        assert cs.count_commits() == 0


def test_lines_changed():
    mock_output = "10\t5\tfile1.py\n20\t3\tfile2.py"
    with patch("sentinel.code_stats.subprocess.run",
               return_value=MagicMock(returncode=0, stdout=mock_output)):
        result = cs.lines_changed()
        assert result["added"] == 30
        assert result["deleted"] == 8


def test_top_files():
    mock_output = "file1.py\nfile2.py\nfile1.py"
    with patch("sentinel.code_stats.subprocess.run",
               return_value=MagicMock(returncode=0, stdout=mock_output)):
        top = cs.top_files()
        assert top[0]["file"] == "file1.py"
        assert top[0]["changes"] == 2


def test_commit_streak_empty():
    with patch("sentinel.code_stats.subprocess.run",
               return_value=MagicMock(returncode=0, stdout="")):
        assert cs.commit_streak() == 0


def test_log_daily_stats(conn):
    with patch("sentinel.code_stats.count_commits", return_value=5):
        with patch("sentinel.code_stats.lines_changed",
                   return_value={"added": 100, "deleted": 20}):
            sid = cs.log_daily_stats(conn)
            assert sid > 0


def test_get_stats_log(conn):
    with patch("sentinel.code_stats.count_commits", return_value=3):
        with patch("sentinel.code_stats.lines_changed",
                   return_value={"added": 50, "deleted": 10}):
            cs.log_daily_stats(conn)
    log = cs.get_stats_log(conn)
    assert len(log) == 1


def test_weekly_summary(conn):
    with patch("sentinel.code_stats.count_commits", return_value=3):
        with patch("sentinel.code_stats.lines_changed",
                   return_value={"added": 50, "deleted": 10}):
            cs.log_daily_stats(conn)
    summary = cs.weekly_summary(conn)
    assert summary["commits"] == 3
    assert summary["lines_added"] == 50
    assert summary["net_lines"] == 40
