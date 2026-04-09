"""Tests for sentinel.snapshots."""
import time
import pytest
from sentinel import snapshots, db


def test_take_snapshot_returns_id(conn):
    sid = snapshots.take_snapshot(conn, trigger="manual")
    assert isinstance(sid, int) and sid > 0


def test_take_snapshot_default_trigger(conn):
    sid = snapshots.take_snapshot(conn)
    snap = snapshots.get_snapshot(conn, sid)
    assert snap["trigger"] == "manual"


def test_get_snapshot_returns_dict(conn):
    sid = snapshots.take_snapshot(conn, "test")
    snap = snapshots.get_snapshot(conn, sid)
    assert snap["id"] == sid
    assert "state" in snap
    assert isinstance(snap["state"], dict)


def test_get_snapshot_missing_returns_none(conn):
    snapshots._ensure_table(conn)
    assert snapshots.get_snapshot(conn, 9999) is None


def test_snapshot_captures_rules(conn):
    db.add_rule(conn, "block youtube")
    sid = snapshots.take_snapshot(conn, "r")
    snap = snapshots.get_snapshot(conn, sid)
    assert len(snap["state"]["rules"]) == 1
    assert snap["state"]["rules"][0]["text"] == "block youtube"


def test_snapshot_captures_goals(conn):
    from sentinel import stats
    stats.add_goal(conn, "g1", "max_visits", 5)
    sid = snapshots.take_snapshot(conn)
    snap = snapshots.get_snapshot(conn, sid)
    assert len(snap["state"]["goals"]) == 1


def test_snapshot_captures_config(conn):
    db.set_config(conn, "k", "v")
    sid = snapshots.take_snapshot(conn)
    snap = snapshots.get_snapshot(conn, sid)
    assert snap["state"]["config"]["k"] == "v"


def test_snapshot_captures_blocked(conn):
    from sentinel import blocker
    blocker._blocked_apps.add("com.test")
    sid = snapshots.take_snapshot(conn)
    snap = snapshots.get_snapshot(conn, sid)
    assert "com.test" in snap["state"]["blocked"]["apps"]


def test_list_snapshots_empty(conn):
    snapshots._ensure_table(conn)
    assert snapshots.list_snapshots(conn) == []


def test_list_snapshots_ordering(conn):
    a = snapshots.take_snapshot(conn, "a")
    b = snapshots.take_snapshot(conn, "b")
    lst = snapshots.list_snapshots(conn)
    assert lst[0]["id"] == b
    assert lst[1]["id"] == a


def test_list_snapshots_limit(conn):
    for i in range(5):
        snapshots.take_snapshot(conn, f"t{i}")
    assert len(snapshots.list_snapshots(conn, limit=3)) == 3


def test_diff_snapshots_added_rule(conn):
    a = snapshots.take_snapshot(conn, "a")
    db.add_rule(conn, "new rule")
    b = snapshots.take_snapshot(conn, "b")
    d = snapshots.diff_snapshots(conn, a, b)
    assert len(d["rules"]["added"]) == 1
    assert len(d["rules"]["removed"]) == 0


def test_diff_snapshots_removed_rule(conn):
    rid = db.add_rule(conn, "r")
    a = snapshots.take_snapshot(conn, "a")
    db.delete_rule(conn, rid)
    b = snapshots.take_snapshot(conn, "b")
    d = snapshots.diff_snapshots(conn, a, b)
    assert len(d["rules"]["removed"]) == 1


def test_diff_snapshots_config_changed(conn):
    db.set_config(conn, "k", "v1")
    a = snapshots.take_snapshot(conn, "a")
    db.set_config(conn, "k", "v2")
    b = snapshots.take_snapshot(conn, "b")
    d = snapshots.diff_snapshots(conn, a, b)
    assert "k" in d["config_changed"]


def test_diff_snapshots_missing(conn):
    snapshots._ensure_table(conn)
    d = snapshots.diff_snapshots(conn, 1, 2)
    assert "error" in d


def test_delete_snapshot(conn):
    sid = snapshots.take_snapshot(conn)
    snapshots.delete_snapshot(conn, sid)
    assert snapshots.get_snapshot(conn, sid) is None


def test_periodic_snapshot_first_call(conn):
    result = snapshots.periodic_snapshot(conn, interval_hours=24)
    assert result["taken"] is True
    assert result["id"] is not None


def test_periodic_snapshot_skips_within_interval(conn):
    snapshots.periodic_snapshot(conn, interval_hours=24)
    result = snapshots.periodic_snapshot(conn, interval_hours=24)
    assert result["taken"] is False
