"""Tests for sentinel.screen — Frozen Turkey state primitive."""
import json
import time
import pytest

from sentinel import screen, db


def test_default_state_inactive(conn):
    s = screen.get_state(conn)
    assert s["active"] is False
    assert s["until_ts"] is None


def test_lock_returns_active_state(conn):
    s = screen.lock(conn, 60, "deep work")
    assert s["active"] is True
    assert s["until_ts"] > time.time()
    assert s["message"] == "deep work"
    assert s["remaining_seconds"] > 0
    assert s["remaining_seconds"] <= 60


def test_lock_persists_in_config(conn):
    screen.lock(conn, 60, "x")
    raw = db.get_config(conn, screen.CFG_KEY)
    parsed = json.loads(raw)
    assert parsed["active"] is True


def test_is_active_after_lock(conn):
    screen.lock(conn, 60, "x")
    assert screen.is_active(conn) is True


def test_lock_rejects_zero_duration(conn):
    with pytest.raises(ValueError):
        screen.lock(conn, 0, "x")


def test_lock_rejects_negative_duration(conn):
    with pytest.raises(ValueError):
        screen.lock(conn, -1, "x")


def test_expired_state_returns_inactive(conn):
    """Manually expire and verify get_state cleans up + returns inactive."""
    screen.lock(conn, 60, "x")
    # Backdate
    state = json.loads(db.get_config(conn, screen.CFG_KEY))
    state["until_ts"] = time.time() - 1
    db.set_config(conn, screen.CFG_KEY, json.dumps(state))
    s = screen.get_state(conn)
    assert s["active"] is False
    # And the config row should be cleared
    assert db.get_config(conn, screen.CFG_KEY) == ""


def test_lock_extends_when_longer(conn):
    """Re-locking with a longer duration extends until_ts."""
    s1 = screen.lock(conn, 60, "first")
    time.sleep(0.01)
    s2 = screen.lock(conn, 3600, "second")
    assert s2["until_ts"] >= s1["until_ts"]


def test_lock_does_not_shorten(conn):
    """Re-locking with a shorter duration keeps the existing longer one."""
    s1 = screen.lock(conn, 3600, "long one")
    s2 = screen.lock(conn, 60, "short attempt")
    # The until_ts should still be the longer one
    assert s2["until_ts"] == s1["until_ts"]
    # And the message should be preserved
    assert s2["message"] == "long one"


def test_end_lockout_refused_without_force(conn):
    screen.lock(conn, 3600, "x")
    assert screen.end_lockout(conn, force=False) is False
    assert screen.is_active(conn) is True


def test_end_lockout_force_works(conn):
    screen.lock(conn, 3600, "x")
    assert screen.end_lockout(conn, force=True) is True
    assert screen.is_active(conn) is False


def test_end_lockout_when_inactive_returns_true(conn):
    """Ending an already-inactive lockout is a no-op success."""
    assert screen.end_lockout(conn, force=False) is True


def test_state_includes_started_at(conn):
    screen.lock(conn, 60, "x")
    s = screen.get_state(conn)
    assert s["started_at"] is not None


def test_state_started_at_preserved_on_extend(conn):
    """The original start time survives a later extension."""
    s1 = screen.lock(conn, 60, "x")
    time.sleep(0.05)
    s2 = screen.lock(conn, 3600, "x")
    assert s2["started_at"] == s1["started_at"]


def test_state_recovers_from_corrupt_config(conn):
    """Garbage in the config row → returns inactive instead of crashing."""
    db.set_config(conn, screen.CFG_KEY, "this is not json")
    s = screen.get_state(conn)
    assert s["active"] is False
