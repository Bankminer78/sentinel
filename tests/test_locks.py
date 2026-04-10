"""Tests for sentinel.locks — write-once commitments with friction gates."""
import time
import pytest
from unittest.mock import patch

from sentinel import locks, blocker, ai_store

# ---------------------------------------------------------------------------
# Schema + CRUD
# ---------------------------------------------------------------------------

def test_create_returns_id(conn):
    lid = locks.create(conn, "no twitter", "no_unblock_domain",
                       target="twitter.com", duration_seconds=3600)
    assert lid > 0

def test_create_persists(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600)
    lk = locks.get(conn, lid)
    assert lk["name"] == "x"
    assert lk["kind"] == "no_unblock_domain"
    assert lk["target"] == "x.com"
    assert lk["until_ts"] > time.time()
    assert lk["released_at"] is None
    assert lk["friction"] is None

def test_create_with_friction_serializes(conn):
    lid = locks.create(conn, "y", "no_unblock_domain", "y.com", 3600,
                       friction={"type": "wait", "seconds": 600})
    lk = locks.get(conn, lid)
    assert lk["friction"] == {"type": "wait", "seconds": 600}

def test_create_target_can_be_none(conn):
    """A kind-wide lock matches every target."""
    lid = locks.create(conn, "no unblocks at all", "no_unblock_domain",
                       target=None, duration_seconds=3600)
    lk = locks.get(conn, lid)
    assert lk["target"] is None

def test_create_rejects_empty_name(conn):
    with pytest.raises(ValueError):
        locks.create(conn, "", "no_unblock_domain", "x.com", 3600)

def test_create_rejects_empty_kind(conn):
    with pytest.raises(ValueError):
        locks.create(conn, "x", "", "x.com", 3600)

def test_create_rejects_zero_duration(conn):
    with pytest.raises(ValueError):
        locks.create(conn, "x", "no_unblock_domain", "x.com", 0)

def test_create_rejects_negative_duration(conn):
    with pytest.raises(ValueError):
        locks.create(conn, "x", "no_unblock_domain", "x.com", -1)

@pytest.mark.parametrize("friction", [
    {"type": "unknown_type", "seconds": 60},
    {"type": "wait"},  # missing seconds
    {"type": "wait", "seconds": 0},
    {"type": "wait", "seconds": "not a number"},
    {"type": "type_text"},  # missing chars
    {"type": "type_text", "chars": 5},  # below min
    {"type": "type_text", "chars": 5000},  # above max
    {"missing_type_key": True},
    "not a dict",
])
def test_create_rejects_bad_friction(conn, friction):
    with pytest.raises(ValueError):
        locks.create(conn, "x", "no_unblock_domain", "x.com", 60,
                     friction=friction)

def test_create_accepts_float_duration_truncated(conn):
    """Float seconds work and are stored as a real."""
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 60.5)
    lk = locks.get(conn, lid)
    assert lk["until_ts"] > time.time()

def test_get_missing_returns_none(conn):
    assert locks.get(conn, 99999) is None

# ---------------------------------------------------------------------------
# is_locked
# ---------------------------------------------------------------------------

def test_is_locked_no_locks(conn):
    assert locks.is_locked(conn, "no_unblock_domain", "x.com") is False

def test_is_locked_exact_target(conn):
    locks.create(conn, "x", "no_unblock_domain", "x.com", 3600)
    assert locks.is_locked(conn, "no_unblock_domain", "x.com") is True
    assert locks.is_locked(conn, "no_unblock_domain", "y.com") is False

def test_is_locked_kind_mismatch(conn):
    locks.create(conn, "x", "no_unblock_domain", "x.com", 3600)
    assert locks.is_locked(conn, "no_unblock_app", "x.com") is False

def test_is_locked_kind_wide_matches_any_target(conn):
    """A lock with target=NULL matches every is_locked check for that kind."""
    locks.create(conn, "no unblocks at all", "no_unblock_domain",
                 target=None, duration_seconds=3600)
    assert locks.is_locked(conn, "no_unblock_domain", "x.com") is True
    assert locks.is_locked(conn, "no_unblock_domain", "y.com") is True
    assert locks.is_locked(conn, "no_unblock_domain", "literally-anything.com") is True

def test_is_locked_kind_wide_check_without_target(conn):
    locks.create(conn, "x", "no_pause", target=None, duration_seconds=3600)
    assert locks.is_locked(conn, "no_pause") is True
    assert locks.is_locked(conn, "no_pause", target=None) is True

def test_is_locked_expired_returns_false(conn):
    locks.create(conn, "x", "no_unblock_domain", "x.com", 3600)
    # Manually expire
    conn.execute("UPDATE locks SET until_ts=? WHERE 1=1", (time.time() - 1,))
    conn.commit()
    assert locks.is_locked(conn, "no_unblock_domain", "x.com") is False

def test_is_locked_released_returns_false(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600)
    conn.execute("UPDATE locks SET released_at=? WHERE id=?", (time.time(), lid))
    conn.commit()
    assert locks.is_locked(conn, "no_unblock_domain", "x.com") is False

# ---------------------------------------------------------------------------
# list / cleanup / delete
# ---------------------------------------------------------------------------

def test_list_active_excludes_expired(conn):
    locks.create(conn, "active", "no_unblock_domain", "a.com", 3600)
    lid = locks.create(conn, "expired", "no_unblock_domain", "b.com", 3600)
    conn.execute("UPDATE locks SET until_ts=? WHERE id=?",
                 (time.time() - 1, lid))
    conn.commit()
    active = locks.list_active(conn)
    assert len(active) == 1
    assert active[0]["name"] == "active"

def test_list_active_filters_by_kind(conn):
    locks.create(conn, "dom", "no_unblock_domain", "a.com", 3600)
    locks.create(conn, "app", "no_unblock_app", "com.app", 3600)
    out = locks.list_active(conn, kind="no_unblock_domain")
    assert len(out) == 1
    assert out[0]["name"] == "dom"

def test_list_all_includes_released(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600)
    conn.execute("UPDATE locks SET released_at=? WHERE id=?", (time.time(), lid))
    conn.commit()
    all_ = locks.list_all(conn)
    assert len(all_) == 1

def test_cleanup_marks_expired(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600)
    conn.execute("UPDATE locks SET until_ts=? WHERE id=?", (time.time() - 1, lid))
    conn.commit()
    n = locks.cleanup_expired(conn)
    assert n == 1
    assert locks.get(conn, lid)["released_at"] is not None

def test_cleanup_idempotent(conn):
    locks.create(conn, "x", "no_unblock_domain", "x.com", 3600)
    locks.cleanup_expired(conn)
    n = locks.cleanup_expired(conn)
    assert n == 0

def test_delete_refused_when_active(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600)
    assert locks.delete(conn, lid) is False
    assert locks.get(conn, lid) is not None

def test_delete_allowed_when_expired(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600)
    conn.execute("UPDATE locks SET until_ts=? WHERE id=?", (time.time() - 1, lid))
    conn.commit()
    assert locks.delete(conn, lid) is True
    assert locks.get(conn, lid) is None

def test_delete_allowed_when_released(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600)
    conn.execute("UPDATE locks SET released_at=? WHERE id=?", (time.time(), lid))
    conn.commit()
    assert locks.delete(conn, lid) is True

def test_delete_missing_returns_false(conn):
    assert locks.delete(conn, 99999) is False

# ---------------------------------------------------------------------------
# Friction: wait
# ---------------------------------------------------------------------------

def test_request_release_no_friction_refuses(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600,
                       friction=None)
    out = locks.request_release(conn, lid)
    assert "error" in out
    assert "no early release" in out["error"]

def test_request_release_expired_releases_immediately(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600)
    conn.execute("UPDATE locks SET until_ts=? WHERE id=?", (time.time() - 1, lid))
    conn.commit()
    out = locks.request_release(conn, lid)
    assert out.get("released") is True
    assert out["reason"] == "expired"
    assert locks.get(conn, lid)["released_at"] is not None

def test_wait_friction_returns_challenge(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600,
                       friction={"type": "wait", "seconds": 60})
    out = locks.request_release(conn, lid)
    assert "challenge" in out
    assert out["challenge"]["type"] == "wait"
    assert out["challenge"]["wait_seconds"] == 60
    assert "token" in out["challenge"]
    assert "unlock_at" in out["challenge"]

def test_wait_friction_too_early_refuses(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600,
                       friction={"type": "wait", "seconds": 60})
    challenge = locks.request_release(conn, lid)["challenge"]
    out = locks.complete_release(conn, lid, challenge["token"])
    assert "error" in out
    assert "wait period" in out["error"]
    assert "remaining_seconds" in out
    assert locks.get(conn, lid)["released_at"] is None

def test_wait_friction_after_elapsed_succeeds(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600,
                       friction={"type": "wait", "seconds": 5})
    challenge = locks.request_release(conn, lid)["challenge"]
    # Fast-forward by rewriting challenge_started_at
    conn.execute("UPDATE locks SET challenge_started_at=? WHERE id=?",
                 (time.time() - 10, lid))
    conn.commit()
    out = locks.complete_release(conn, lid, challenge["token"])
    assert out.get("released") is True
    assert locks.get(conn, lid)["released_at"] is not None

# ---------------------------------------------------------------------------
# Friction: type_text
# ---------------------------------------------------------------------------

def test_type_text_returns_random_text(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600,
                       friction={"type": "type_text", "chars": 50})
    out = locks.request_release(conn, lid)
    assert "challenge" in out
    spec = out["challenge"]
    assert spec["type"] == "type_text"
    assert len(spec["text"]) == 50
    assert spec["chars"] == 50

def test_type_text_two_calls_return_different_text(conn):
    """Each call generates a fresh random string — no replay."""
    lid1 = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600,
                        friction={"type": "type_text", "chars": 100})
    lid2 = locks.create(conn, "y", "no_unblock_domain", "y.com", 3600,
                        friction={"type": "type_text", "chars": 100})
    a = locks.request_release(conn, lid1)["challenge"]["text"]
    b = locks.request_release(conn, lid2)["challenge"]["text"]
    assert a != b

def test_type_text_correct_response_releases(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600,
                       friction={"type": "type_text", "chars": 20})
    challenge = locks.request_release(conn, lid)["challenge"]
    out = locks.complete_release(conn, lid, challenge["token"], challenge["text"])
    assert out.get("released") is True
    assert locks.get(conn, lid)["released_at"] is not None

def test_type_text_wrong_response_refuses(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600,
                       friction={"type": "type_text", "chars": 20})
    challenge = locks.request_release(conn, lid)["challenge"]
    out = locks.complete_release(conn, lid, challenge["token"], "wrong text")
    assert "error" in out
    assert locks.get(conn, lid)["released_at"] is None

def test_type_text_case_sensitive(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600,
                       friction={"type": "type_text", "chars": 20})
    challenge = locks.request_release(conn, lid)["challenge"]
    out = locks.complete_release(conn, lid, challenge["token"],
                                 challenge["text"].lower())
    # Random text contains both cases — lowering it almost certainly mismatches
    assert "error" in out

# ---------------------------------------------------------------------------
# Challenge token security
# ---------------------------------------------------------------------------

def test_complete_with_wrong_token_refused(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600,
                       friction={"type": "type_text", "chars": 20})
    locks.request_release(conn, lid)  # generates real token
    out = locks.complete_release(conn, lid, "fake-token-here", "anything")
    assert "error" in out
    assert "token" in out["error"]

def test_complete_without_request_refused(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600,
                       friction={"type": "type_text", "chars": 20})
    out = locks.complete_release(conn, lid, "any-token", "any-response")
    assert "error" in out

def test_double_release_returns_already_released(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600,
                       friction={"type": "type_text", "chars": 20})
    challenge = locks.request_release(conn, lid)["challenge"]
    locks.complete_release(conn, lid, challenge["token"], challenge["text"])
    # Second attempt
    out = locks.complete_release(conn, lid, challenge["token"], challenge["text"])
    assert out.get("already_released") is True

def test_request_release_after_release_returns_already_released(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600,
                       friction={"type": "wait", "seconds": 60})
    conn.execute("UPDATE locks SET released_at=? WHERE id=?", (time.time(), lid))
    conn.commit()
    out = locks.request_release(conn, lid)
    assert out.get("already_released") is True

# ---------------------------------------------------------------------------
# Integration: blocker honors locks
# ---------------------------------------------------------------------------

def test_blocker_unblock_refused_when_locked(conn):
    blocker.block_domain("evil.com")
    locks.create(conn, "x", "no_unblock_domain", "evil.com", 3600)
    with patch("sentinel.blocker._sync_hosts"):
        ok = blocker.unblock_domain("evil.com", conn=conn)
    assert ok is False
    assert blocker.is_blocked_domain("evil.com") is True

def test_blocker_unblock_succeeds_when_not_locked(conn):
    blocker.block_domain("ok.com")
    with patch("sentinel.blocker._sync_hosts"):
        ok = blocker.unblock_domain("ok.com", conn=conn)
    assert ok is True
    assert blocker.is_blocked_domain("ok.com") is False

def test_blocker_unblock_force_bypasses_lock(conn):
    blocker.block_domain("evil.com")
    locks.create(conn, "x", "no_unblock_domain", "evil.com", 3600)
    with patch("sentinel.blocker._sync_hosts"):
        ok = blocker.unblock_domain("evil.com", conn=conn, force=True)
    assert ok is True
    assert blocker.is_blocked_domain("evil.com") is False

def test_blocker_unblock_no_conn_skips_check(conn):
    """Without a conn, blocker is unaware of locks (used by tests / startup)."""
    blocker.block_domain("evil.com")
    locks.create(conn, "x", "no_unblock_domain", "evil.com", 3600)
    with patch("sentinel.blocker._sync_hosts"):
        ok = blocker.unblock_domain("evil.com")  # no conn
    assert ok is True

def test_blocker_unblock_app_refused_when_locked(conn):
    blocker.block_app("com.evil.app")
    locks.create(conn, "x", "no_unblock_app", "com.evil.app", 3600)
    ok = blocker.unblock_app("com.evil.app", conn=conn)
    assert ok is False
    assert blocker.is_blocked_app("com.evil.app") is True

def test_blocker_kind_wide_lock_blocks_any_unblock(conn):
    """A target=NULL lock makes ALL unblocks fail."""
    blocker.block_domain("a.com")
    blocker.block_domain("b.com")
    locks.create(conn, "no escape", "no_unblock_domain", target=None,
                 duration_seconds=3600)
    with patch("sentinel.blocker._sync_hosts"):
        assert blocker.unblock_domain("a.com", conn=conn) is False
        assert blocker.unblock_domain("b.com", conn=conn) is False

# ---------------------------------------------------------------------------
# Integration: triggers honor locks
# ---------------------------------------------------------------------------

