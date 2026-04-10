"""Tests for sentinel.emergency — the rate-limited out switch."""
import time
from datetime import datetime
import pytest
from unittest.mock import patch

from sentinel import emergency, locks, screen, ai_store, db


# --- Limit / status ---

def test_default_limit(conn):
    assert emergency.get_limit(conn) == emergency.DEFAULT_MONTHLY_LIMIT


def test_set_limit(conn):
    emergency.set_limit(conn, 5)
    assert emergency.get_limit(conn) == 5


def test_set_limit_zero_allowed(conn):
    emergency.set_limit(conn, 0)
    assert emergency.get_limit(conn) == 0


def test_set_limit_rejects_negative(conn):
    with pytest.raises(ValueError):
        emergency.set_limit(conn, -1)


def test_remaining_full_when_unused(conn):
    assert emergency.remaining(conn) == emergency.DEFAULT_MONTHLY_LIMIT


def test_status_shape(conn):
    s = emergency.status(conn)
    assert "limit" in s
    assert "used_this_month" in s
    assert "remaining" in s
    assert "month_start_ts" in s


# --- Trigger refused without reason ---

def test_trigger_requires_reason(conn):
    out = emergency.trigger(conn, "")
    assert out["ok"] is False
    assert "reason" in out["error"]


def test_trigger_rejects_whitespace_reason(conn):
    out = emergency.trigger(conn, "   ")
    assert out["ok"] is False


def test_trigger_with_no_locks(conn):
    out = emergency.trigger(conn, "feeling overwhelmed")
    assert out["ok"] is True
    assert out["released_count"] == 0
    assert out["remaining"] == emergency.DEFAULT_MONTHLY_LIMIT - 1


# --- Trigger releases active locks ---

def test_trigger_releases_all_locks_by_default(conn):
    locks.create(conn, "a", "no_unblock_domain", "a.com", 3600)
    locks.create(conn, "b", "no_unblock_domain", "b.com", 3600)
    locks.create(conn, "c", "no_delete_trigger", "x", 3600)
    out = emergency.trigger(conn, "need a break")
    assert out["ok"] is True
    assert out["released_count"] == 3
    assert len(out["released_locks"]) == 3
    # All should now be released
    assert len(locks.list_active(conn)) == 0


def test_trigger_filters_by_kinds(conn):
    locks.create(conn, "a", "no_unblock_domain", "a.com", 3600)
    locks.create(conn, "b", "no_delete_trigger", "x", 3600)
    out = emergency.trigger(conn, "ok", kinds=["no_unblock_domain"])
    assert out["released_count"] == 1
    # the no_delete_trigger lock should still be active
    assert len(locks.list_active(conn, kind="no_delete_trigger")) == 1


def test_trigger_releases_bypass_friction(conn):
    """A lock with type_text friction is still released by emergency exit."""
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600,
                       friction={"type": "type_text", "chars": 200})
    emergency.trigger(conn, "crisis")
    lk = locks.get(conn, lid)
    assert lk["released_at"] is not None


def test_trigger_ends_screen_lockout(conn):
    screen.lock(conn, 3600, "deep work")
    assert screen.is_active(conn) is True
    out = emergency.trigger(conn, "real emergency")
    assert out["screen_lockout_ended"] is True
    assert screen.is_active(conn) is False


def test_trigger_with_kinds_excluding_screen_keeps_lockout(conn):
    screen.lock(conn, 3600, "deep work")
    locks.create(conn, "x", "no_unblock_domain", "x.com", 3600)
    emergency.trigger(conn, "ok", kinds=["no_unblock_domain"])
    assert screen.is_active(conn) is True  # not in kinds list


# --- Counter / monthly limit ---

def test_counter_increments(conn):
    emergency.trigger(conn, "first")
    assert emergency.get_used_this_month(conn) == 1
    emergency.trigger(conn, "second")
    assert emergency.get_used_this_month(conn) == 2


def test_remaining_decreases(conn):
    initial = emergency.remaining(conn)
    emergency.trigger(conn, "use one")
    assert emergency.remaining(conn) == initial - 1


def test_refused_when_exhausted(conn):
    emergency.set_limit(conn, 2)
    emergency.trigger(conn, "first")
    emergency.trigger(conn, "second")
    out = emergency.trigger(conn, "third")
    assert out["ok"] is False
    assert "remaining" in out["error"]
    assert "next_reset_ts" in out


def test_zero_limit_blocks_all(conn):
    emergency.set_limit(conn, 0)
    out = emergency.trigger(conn, "any reason")
    assert out["ok"] is False


# --- History ---

def test_history_records_each_exit(conn):
    emergency.trigger(conn, "reason A")
    emergency.trigger(conn, "reason B")
    h = emergency.history(conn)
    assert len(h) == 2
    reasons = [d["doc"]["reason"] for d in h]
    assert "reason A" in reasons
    assert "reason B" in reasons


def test_history_records_kinds(conn):
    emergency.trigger(conn, "x", kinds=["no_unblock_domain"])
    h = emergency.history(conn)
    assert h[0]["doc"]["kinds"] == ["no_unblock_domain"]


def test_history_records_released_count(conn):
    locks.create(conn, "a", "no_unblock_domain", "a.com", 3600)
    locks.create(conn, "b", "no_unblock_domain", "b.com", 3600)
    emergency.trigger(conn, "x")
    h = emergency.history(conn)
    assert h[0]["doc"]["released_count"] == 2


def test_history_records_screen_lockout_ended(conn):
    screen.lock(conn, 3600, "x")
    emergency.trigger(conn, "x")
    h = emergency.history(conn)
    assert h[0]["doc"]["screen_lockout_ended"] is True


# --- Monthly reset ---

def test_used_this_month_only_counts_current_month(conn):
    """Old logged exits from a previous month don't count."""
    # Insert a fake old exit by directly writing to ai_docs
    old_ts = time.time() - 60 * 86400  # 60 days ago
    ai_store.doc_add(conn, emergency.LOG_NAMESPACE, {"reason": "old"})
    # Backdate it
    conn.execute(
        "UPDATE ai_docs SET created_at=? WHERE namespace=?",
        (old_ts, emergency.LOG_NAMESPACE))
    conn.commit()
    assert emergency.get_used_this_month(conn) == 0
    emergency.trigger(conn, "new")
    assert emergency.get_used_this_month(conn) == 1
