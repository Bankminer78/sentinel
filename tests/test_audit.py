"""Tests for sentinel.audit."""
import pytest
import time
from sentinel import audit, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_log_action(conn):
    aid = audit.log_action(conn, "test_action", {"key": "value"})
    assert aid > 0


def test_get_audit_log(conn):
    audit.log_action(conn, "action1", {})
    audit.log_action(conn, "action2", {})
    log = audit.get_audit_log(conn)
    assert len(log) == 2


def test_empty_log(conn):
    assert audit.get_audit_log(conn) == []


def test_hash_chain(conn):
    audit.log_action(conn, "a", {})
    audit.log_action(conn, "b", {})
    audit.log_action(conn, "c", {})
    assert audit.verify_chain(conn) is True


def test_chain_tampered(conn):
    audit.log_action(conn, "a", {})
    audit.log_action(conn, "b", {})
    # Tamper with the stored record
    conn.execute("UPDATE audit_log SET action='x' WHERE id=1")
    conn.commit()
    assert audit.verify_chain(conn) is False


def test_empty_chain_valid(conn):
    assert audit.verify_chain(conn) is True


def test_get_last_hash_empty(conn):
    assert audit.get_last_hash(conn) == ""


def test_get_last_hash_after_log(conn):
    audit.log_action(conn, "test", {})
    assert audit.get_last_hash(conn)


def test_log_limit(conn):
    for i in range(20):
        audit.log_action(conn, f"action_{i}", {})
    log = audit.get_audit_log(conn, limit=5)
    assert len(log) == 5


def test_search_audit(conn):
    audit.log_action(conn, "login", {"user": "alice"})
    audit.log_action(conn, "logout", {"user": "bob"})
    results = audit.search_audit(conn, "login")
    assert len(results) == 1


def test_search_no_match(conn):
    audit.log_action(conn, "test", {})
    assert audit.search_audit(conn, "nothing") == []


def test_details_parsed(conn):
    audit.log_action(conn, "test", {"a": 1, "b": "x"})
    log = audit.get_audit_log(conn)
    assert log[0]["details"] == {"a": 1, "b": "x"}


def test_purge_old(conn):
    # First log something to ensure table exists
    audit.log_action(conn, "recent", {})
    # Then insert old entry directly
    old_ts = time.time() - 100 * 86400
    conn.execute(
        "INSERT INTO audit_log (action,details,ts,prev_hash,hash) VALUES (?,?,?,?,?)",
        ("old", "{}", old_ts, "", "abc"))
    conn.commit()
    count = audit.purge_old(conn, days=90)
    assert count >= 1


def test_hash_chain_after_many_entries(conn):
    for i in range(50):
        audit.log_action(conn, f"action_{i}", {"i": i})
    assert audit.verify_chain(conn) is True


def test_descending_order(conn):
    audit.log_action(conn, "first", {})
    audit.log_action(conn, "second", {})
    log = audit.get_audit_log(conn)
    assert log[0]["action"] == "second"  # Most recent first
