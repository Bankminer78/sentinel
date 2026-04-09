"""Tests for sentinel.recovery."""
import pytest
from unittest.mock import AsyncMock, patch
from sentinel import recovery, classifier


def test_enter_recovery_mode_returns_id(conn):
    rid = recovery.enter_recovery_mode(conn, "slip")
    assert isinstance(rid, int) and rid > 0


def test_enter_recovery_reuses_active(conn):
    a = recovery.enter_recovery_mode(conn, "slip1")
    b = recovery.enter_recovery_mode(conn, "slip2")
    assert a == b


def test_exit_recovery_mode(conn):
    recovery.enter_recovery_mode(conn, "slip")
    recovery.exit_recovery_mode(conn)
    assert recovery.is_in_recovery(conn) is False


def test_exit_recovery_noop_when_inactive(conn):
    recovery._ensure_table(conn)
    recovery.exit_recovery_mode(conn)
    assert recovery.is_in_recovery(conn) is False


def test_is_in_recovery_false_initially(conn):
    assert recovery.is_in_recovery(conn) is False


def test_is_in_recovery_true_when_active(conn):
    recovery.enter_recovery_mode(conn, "slip")
    assert recovery.is_in_recovery(conn) is True


def test_recovery_status_inactive(conn):
    status = recovery.recovery_status(conn)
    assert status["active"] is False


def test_recovery_status_active(conn):
    recovery.enter_recovery_mode(conn, "big slip")
    status = recovery.recovery_status(conn)
    assert status["active"] is True
    assert status["reason"] == "big slip"
    assert status["duration_s"] >= 0


@pytest.mark.asyncio
async def test_suggest_recovery_calls_llm(conn):
    mock_call = AsyncMock(return_value="Take a break.")
    with patch.object(classifier, "call_gemini", mock_call):
        result = await recovery.suggest_recovery(conn, "fake-key", "binge")
        assert result == "Take a break."
        assert mock_call.call_count == 1


@pytest.mark.asyncio
async def test_suggest_recovery_handles_error(conn):
    mock_call = AsyncMock(side_effect=Exception("api down"))
    with patch.object(classifier, "call_gemini", mock_call):
        result = await recovery.suggest_recovery(conn, "fake-key", "slip")
        assert "breath" in result.lower() or "reset" in result.lower()


def test_reset_streak_gracefully(conn):
    conn.execute(
        "INSERT INTO streaks (goal_name, current, longest, last_date) VALUES (?,?,?,?)",
        ("focus", 5, 10, "2024-01-01"))
    conn.commit()
    recovery.reset_streak_gracefully(conn, "focus")
    r = conn.execute("SELECT current, longest FROM streaks WHERE goal_name=?", ("focus",)).fetchone()
    assert r["current"] == 0
    assert r["longest"] == 10


def test_reset_streak_preserves_longest_when_current_higher(conn):
    conn.execute(
        "INSERT INTO streaks (goal_name, current, longest, last_date) VALUES (?,?,?,?)",
        ("gym", 15, 10, "2024-01-01"))
    conn.commit()
    recovery.reset_streak_gracefully(conn, "gym")
    r = conn.execute("SELECT current, longest FROM streaks WHERE goal_name=?", ("gym",)).fetchone()
    assert r["current"] == 0
    assert r["longest"] == 15


def test_reset_streak_missing_is_noop(conn):
    recovery._ensure_table(conn)
    recovery.reset_streak_gracefully(conn, "nonexistent")
    # no exception
