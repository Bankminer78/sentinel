"""Tests for sentinel.undo."""
import pytest
from sentinel import undo, db


def test_record_action(conn):
    uid = undo.record_action(conn, "delete_rule", {"id": 1}, {"id": 1, "text": "x"})
    assert uid > 0


def test_undo_empty(conn):
    assert undo.undo(conn) is None


def test_redo_empty(conn):
    assert undo.redo(conn) is None


def test_get_history_empty(conn):
    assert undo.get_undo_history(conn) == []


def test_get_history_after_record(conn):
    undo.record_action(conn, "delete_rule", {"id": 1}, {"id": 1, "text": "x"})
    hist = undo.get_undo_history(conn)
    assert len(hist) == 1
    assert hist[0]["action_type"] == "delete_rule"


def test_undo_delete_rule(conn):
    rid = db.add_rule(conn, "block youtube.com")
    rule = dict(conn.execute("SELECT * FROM rules WHERE id=?", (rid,)).fetchone())
    undo.record_action(conn, "delete_rule", {"id": rid}, rule)
    db.delete_rule(conn, rid)
    assert db.get_rules(conn, active_only=False) == []
    undone = undo.undo(conn)
    assert undone["action_type"] == "delete_rule"
    rules = db.get_rules(conn, active_only=False)
    assert len(rules) == 1


def test_undo_toggle_rule(conn):
    rid = db.add_rule(conn, "block x")
    # Currently active=1. Record undo_data to revert to 1, payload target 0 after toggle.
    undo.record_action(conn, "toggle_rule",
                       {"id": rid}, {"id": rid, "active": 1})
    db.toggle_rule(conn, rid)
    assert db.get_rules(conn, active_only=False)[0]["active"] == 0
    undo.undo(conn)
    assert db.get_rules(conn, active_only=False)[0]["active"] == 1


def test_undo_clear_seen(conn):
    db.save_seen(conn, "yt.com", "social")
    seen = [dict(r) for r in conn.execute("SELECT * FROM seen_domains").fetchall()]
    undo.record_action(conn, "clear_seen", {}, {"domains": seen})
    conn.execute("DELETE FROM seen_domains")
    conn.commit()
    undo.undo(conn)
    assert db.get_seen(conn, "yt.com") == "social"


def test_undo_marks_undone(conn):
    rid = db.add_rule(conn, "block x")
    rule = dict(conn.execute("SELECT * FROM rules WHERE id=?", (rid,)).fetchone())
    undo.record_action(conn, "delete_rule", {"id": rid}, rule)
    db.delete_rule(conn, rid)
    undo.undo(conn)
    hist = undo.get_undo_history(conn)
    assert hist[0]["undone"] == 1


def test_redo_after_undo(conn):
    rid = db.add_rule(conn, "block x")
    rule = dict(conn.execute("SELECT * FROM rules WHERE id=?", (rid,)).fetchone())
    undo.record_action(conn, "delete_rule", {"id": rid}, rule)
    db.delete_rule(conn, rid)
    undo.undo(conn)
    assert len(db.get_rules(conn, active_only=False)) == 1
    undo.redo(conn)
    assert db.get_rules(conn, active_only=False) == []


def test_undo_only_most_recent(conn):
    undo.record_action(conn, "toggle_rule", {"id": 1}, {"id": 1, "active": 1})
    undo.record_action(conn, "toggle_rule", {"id": 2}, {"id": 2, "active": 1})
    db.add_rule(conn, "a")
    db.add_rule(conn, "b")
    db.toggle_rule(conn, 1)
    db.toggle_rule(conn, 2)
    entry = undo.undo(conn)
    assert entry["payload"]["id"] == 2


def test_clear_undo_history(conn):
    undo.record_action(conn, "delete_rule", {}, {})
    undo.clear_undo_history(conn)
    assert undo.get_undo_history(conn) == []


def test_history_limit(conn):
    for i in range(5):
        undo.record_action(conn, "delete_rule", {"id": i}, {"id": i})
    hist = undo.get_undo_history(conn, limit=3)
    assert len(hist) == 3
