"""Tests for sentinel.leaderboard."""
import pytest
from datetime import datetime, timedelta
from sentinel import leaderboard, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_record_score(conn):
    leaderboard.record_score(conn, "alice", "2026-04-09", 85.0)
    result = leaderboard.get_leaderboard(conn)
    assert len(result) == 1
    assert result[0]["user"] == "alice"


def test_record_score_update(conn):
    leaderboard.record_score(conn, "alice", "2026-04-09", 50.0)
    leaderboard.record_score(conn, "alice", "2026-04-09", 90.0)
    result = leaderboard.get_leaderboard(conn)
    assert result[0]["avg_score"] == 90.0


def test_leaderboard_ordering(conn):
    today = datetime.now().strftime("%Y-%m-%d")
    leaderboard.record_score(conn, "bob", today, 60.0)
    leaderboard.record_score(conn, "alice", today, 90.0)
    leaderboard.record_score(conn, "carol", today, 75.0)
    result = leaderboard.get_leaderboard(conn)
    assert result[0]["user"] == "alice"
    assert result[-1]["user"] == "bob"


def test_leaderboard_empty(conn):
    assert leaderboard.get_leaderboard(conn) == []


def test_leaderboard_days_filter(conn):
    today = datetime.now().strftime("%Y-%m-%d")
    old_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    leaderboard.record_score(conn, "alice", today, 80.0)
    leaderboard.record_score(conn, "alice", old_date, 20.0)
    result = leaderboard.get_leaderboard(conn, days=7)
    assert result[0]["avg_score"] == 80.0  # Old score filtered out


def test_get_user_stats(conn):
    today = datetime.now().strftime("%Y-%m-%d")
    leaderboard.record_score(conn, "alice", today, 80.0)
    stats = leaderboard.get_user_stats(conn, "alice")
    assert stats["user"] == "alice"
    assert stats["avg_score"] == 80.0
    assert stats["best_score"] == 80.0


def test_get_user_stats_nonexistent(conn):
    stats = leaderboard.get_user_stats(conn, "ghost")
    assert stats["days_tracked"] == 0


def test_leaderboard_avg_calc(conn):
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    leaderboard.record_score(conn, "alice", today, 100.0)
    leaderboard.record_score(conn, "alice", yesterday, 50.0)
    result = leaderboard.get_leaderboard(conn)
    assert result[0]["avg_score"] == 75.0


def test_user_stats_best_worst(conn):
    for i, score in enumerate([50.0, 90.0, 70.0]):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        leaderboard.record_score(conn, "alice", date, score)
    stats = leaderboard.get_user_stats(conn, "alice")
    assert stats["best_score"] == 90.0
    assert stats["worst_score"] == 50.0


def test_days_tracked(conn):
    for i in range(5):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        leaderboard.record_score(conn, "alice", date, 75.0)
    stats = leaderboard.get_user_stats(conn, "alice")
    assert stats["days_tracked"] == 5
