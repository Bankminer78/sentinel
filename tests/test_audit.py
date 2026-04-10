"""Tests for sentinel.audit — append-only audit log + no_delete_audit lock."""
import time
import pytest
from unittest.mock import patch

from sentinel import audit, locks, blocker, triggers, screen, emergency


# ---------------------------------------------------------------------------
# Schema + basic CRUD
# ---------------------------------------------------------------------------


def test_log_creates_row(conn):
    audit.log(conn, "user", "block_domain", {"domain": "x.com"})
    rows = audit.list_recent(conn)
    assert len(rows) == 1
    assert rows[0]["actor"] == "user"
    assert rows[0]["primitive"] == "block_domain"
    assert rows[0]["args_summary"] == {"domain": "x.com"}
    assert rows[0]["result_status"] == "ok"


def test_log_records_timestamp(conn):
    before = time.time()
    audit.log(conn, "user", "x", {})
    after = time.time()
    rows = audit.list_recent(conn)
    assert before <= rows[0]["ts"] <= after


def test_log_with_status(conn):
    audit.log(conn, "user", "x", {}, status="locked")
    assert audit.list_recent(conn)[0]["result_status"] == "locked"


def test_log_handles_none_args(conn):
    audit.log(conn, "user", "x")  # no args
    rows = audit.list_recent(conn)
    assert rows[0]["args_summary"] == {}


def test_list_filters_by_primitive(conn):
    audit.log(conn, "user", "block_domain", {"d": "a.com"})
    audit.log(conn, "user", "unblock_domain", {"d": "a.com"})
    audit.log(conn, "user", "lock.create", {"kind": "x"})
    out = audit.list_recent(conn, primitive="block_domain")
    assert len(out) == 1
    assert out[0]["primitive"] == "block_domain"


def test_list_filters_by_actor(conn):
    audit.log(conn, "user", "x", {})
    audit.log(conn, "trigger:foo", "x", {})
    out = audit.list_recent(conn, actor="trigger:foo")
    assert len(out) == 1


def test_list_orders_newest_first(conn):
    audit.log(conn, "user", "first", {})
    audit.log(conn, "user", "second", {})
    audit.log(conn, "user", "third", {})
    out = audit.list_recent(conn)
    assert [r["primitive"] for r in out] == ["third", "second", "first"]


def test_list_respects_limit(conn):
    for i in range(20):
        audit.log(conn, "user", f"op_{i}", {})
    out = audit.list_recent(conn, limit=5)
    assert len(out) == 5


def test_count_total(conn):
    assert audit.count(conn) == 0
    audit.log(conn, "user", "x", {})
    audit.log(conn, "user", "y", {})
    assert audit.count(conn) == 2


def test_count_since_filter(conn):
    audit.log(conn, "user", "old", {})
    cutoff = time.time() + 0.01
    time.sleep(0.02)
    audit.log(conn, "user", "new", {})
    assert audit.count(conn, since=cutoff) == 1


# ---------------------------------------------------------------------------
# Cleanup gated by no_delete_audit lock
# ---------------------------------------------------------------------------


def test_cleanup_deletes_old_rows(conn):
    audit.log(conn, "user", "old", {})
    # Backdate
    conn.execute("UPDATE agent_audit_log SET ts=? WHERE 1=1", (time.time() - 86400 * 30,))
    conn.commit()
    audit.log(conn, "user", "new", {})
    cutoff = time.time() - 86400  # delete anything older than 1 day
    result = audit.cleanup_older_than(conn, cutoff)
    assert result["ok"] is True
    assert result["deleted"] == 1
    assert audit.count(conn) == 1


def test_cleanup_refused_when_lock_active(conn):
    audit.log(conn, "user", "x", {})
    # Backdate ALL existing rows to 30 days ago so they would be cleanup-eligible
    conn.execute("UPDATE agent_audit_log SET ts=? WHERE 1=1", (time.time() - 86400 * 30,))
    conn.commit()
    before_count = audit.count(conn)
    locks.create(conn, "audit lock", "no_delete_audit", target=None,
                 duration_seconds=3600)
    # locks.create also writes an audit entry (with current ts, so cleanup-ineligible)
    result = audit.cleanup_older_than(conn, time.time() - 86400)  # > 1 day ago
    assert result["ok"] is False
    assert "no_delete_audit" in result["reason"]
    # The old row is still there because cleanup was refused
    after_count = audit.count(conn)
    assert after_count >= before_count  # nothing was deleted


def test_cleanup_works_after_lock_expires(conn):
    audit.log(conn, "user", "x", {})
    conn.execute("UPDATE agent_audit_log SET ts=? WHERE 1=1", (time.time() - 86400 * 30,))
    conn.commit()
    lid = locks.create(conn, "audit lock", "no_delete_audit", target=None,
                       duration_seconds=3600)
    # Manually expire
    conn.execute("UPDATE locks SET until_ts=? WHERE id=?",
                 (time.time() - 1, lid))
    conn.commit()
    result = audit.cleanup_older_than(conn, time.time())
    assert result["ok"] is True


# ---------------------------------------------------------------------------
# Integration: every primitive that mutates state writes an audit entry
# ---------------------------------------------------------------------------


def test_block_domain_logs_audit(conn):
    with patch("sentinel.blocker._sync_hosts"):
        blocker.block_domain("x.com", conn=conn, actor="user")
    rows = audit.list_recent(conn, primitive="block_domain")
    assert len(rows) == 1
    assert rows[0]["args_summary"]["domain"] == "x.com"


def test_unblock_domain_logs_ok(conn):
    blocker.block_domain("x.com")
    with patch("sentinel.blocker._sync_hosts"):
        blocker.unblock_domain("x.com", conn=conn, actor="user")
    rows = audit.list_recent(conn, primitive="unblock_domain")
    assert len(rows) == 1
    assert rows[0]["result_status"] == "ok"


def test_unblock_domain_logs_locked(conn):
    blocker.block_domain("x.com")
    locks.create(conn, "x", "no_unblock_domain", "x.com", 3600)
    with patch("sentinel.blocker._sync_hosts"):
        ok = blocker.unblock_domain("x.com", conn=conn, actor="user")
    assert ok is False
    rows = audit.list_recent(conn, primitive="unblock_domain")
    # Find the locked entry (locks.create also wrote to audit so filter)
    assert any(r["result_status"] == "locked" for r in rows)


def test_unblock_domain_force_logs_forced(conn):
    blocker.block_domain("x.com")
    locks.create(conn, "x", "no_unblock_domain", "x.com", 3600)
    with patch("sentinel.blocker._sync_hosts"):
        blocker.unblock_domain("x.com", conn=conn, actor="user", force=True)
    rows = audit.list_recent(conn, primitive="unblock_domain")
    assert any(r["result_status"] == "forced" for r in rows)


def test_lock_create_logs_audit(conn):
    locks.create(conn, "x", "no_unblock_domain", "x.com", 3600, actor="user")
    rows = audit.list_recent(conn, primitive="lock.create")
    assert len(rows) == 1
    summary = rows[0]["args_summary"]
    assert summary["kind"] == "no_unblock_domain"
    assert summary["target"] == "x.com"
    assert summary["duration_seconds"] == 3600
    assert summary["has_friction"] is False


def test_lock_create_with_friction_records_flag(conn):
    locks.create(conn, "x", "no_unblock_domain", "x.com", 3600,
                 friction={"type": "wait", "seconds": 60})
    rows = audit.list_recent(conn, primitive="lock.create")
    assert rows[0]["args_summary"]["has_friction"] is True


def test_lock_release_logs_audit(conn):
    lid = locks.create(conn, "x", "no_unblock_domain", "x.com", 3600,
                       friction={"type": "type_text", "chars": 20})
    challenge = locks.request_release(conn, lid)["challenge"]
    locks.complete_release(conn, lid, challenge["token"], challenge["text"])
    rows = audit.list_recent(conn, primitive="lock.release")
    assert len(rows) == 1
    assert rows[0]["args_summary"]["lock_id"] == lid


def test_trigger_delete_logs_audit(conn):
    triggers.create(conn, "t", {"steps": [{"call": "now", "save_as": "x"}]},
                    interval_sec=60)
    triggers.delete(conn, "t", actor="user")
    rows = audit.list_recent(conn, primitive="trigger.delete")
    assert len(rows) == 1
    assert rows[0]["args_summary"]["name"] == "t"


def test_trigger_delete_locked_logs_locked(conn):
    triggers.create(conn, "t", {"steps": []}, interval_sec=60)
    locks.create(conn, "x", "no_delete_trigger", "t", 3600)
    triggers.delete(conn, "t", actor="user")
    rows = audit.list_recent(conn, primitive="trigger.delete")
    assert any(r["result_status"] == "locked" for r in rows)


def test_trigger_set_enabled_logs(conn):
    triggers.create(conn, "t", {"steps": []}, interval_sec=60)
    triggers.set_enabled(conn, "t", False, actor="user")
    rows = audit.list_recent(conn, primitive="trigger.set_enabled")
    assert len(rows) == 1
    assert rows[0]["args_summary"]["enabled"] is False


def test_screen_lock_logs(conn):
    screen.lock(conn, 60, "x", actor="user")
    rows = audit.list_recent(conn, primitive="screen_lock")
    assert len(rows) == 1
    assert rows[0]["args_summary"]["duration_seconds"] == 60


def test_emergency_exit_logs(conn):
    emergency.trigger(conn, "test reason")
    rows = audit.list_recent(conn, primitive="emergency_exit")
    assert len(rows) == 1
    # Reason text is NOT stored in audit (only the user-data-free summary)
    assert "reason" not in rows[0]["args_summary"]
    assert "released_count" in rows[0]["args_summary"]


def test_emergency_exit_does_not_leak_reason_text(conn):
    """Reason can contain user data — must not appear in audit summary."""
    canary = "MY_PRIVATE_REASON_TEXT"
    emergency.trigger(conn, canary)
    rows = audit.list_recent(conn, primitive="emergency_exit")
    import json
    assert canary not in json.dumps(rows[0])
