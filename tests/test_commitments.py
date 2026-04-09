"""Tests for sentinel.commitments."""
import datetime as _dt
from sentinel import commitments


def test_create_commitment(conn):
    cid = commitments.create_commitment(conn, "Ship feature", "2099-01-01")
    assert cid > 0


def test_create_with_stakes(conn):
    cid = commitments.create_commitment(conn, "run", "2099-01-01", stakes="$50")
    c = commitments.get_commitment(conn, cid)
    assert c["stakes"] == "$50"


def test_get_commitment(conn):
    cid = commitments.create_commitment(conn, "test", "2099-01-01")
    c = commitments.get_commitment(conn, cid)
    assert c["text"] == "test"
    assert c["status"] == "active"


def test_get_commitment_nonexistent(conn):
    assert commitments.get_commitment(conn, 9999) is None


def test_get_commitments_active(conn):
    commitments.create_commitment(conn, "a", "2099-01-01")
    commitments.create_commitment(conn, "b", "2099-02-01")
    assert len(commitments.get_commitments(conn, "active")) == 2


def test_complete_commitment(conn):
    cid = commitments.create_commitment(conn, "test", "2099-01-01")
    commitments.complete_commitment(conn, cid, proof="done.png")
    c = commitments.get_commitment(conn, cid)
    assert c["status"] == "completed"
    assert c["proof"] == "done.png"


def test_complete_without_proof(conn):
    cid = commitments.create_commitment(conn, "test", "2099-01-01")
    commitments.complete_commitment(conn, cid)
    c = commitments.get_commitment(conn, cid)
    assert c["status"] == "completed"


def test_fail_commitment(conn):
    cid = commitments.create_commitment(conn, "test", "2099-01-01")
    commitments.fail_commitment(conn, cid)
    c = commitments.get_commitment(conn, cid)
    assert c["status"] == "failed"


def test_get_commitments_filter_status(conn):
    cid1 = commitments.create_commitment(conn, "a", "2099-01-01")
    cid2 = commitments.create_commitment(conn, "b", "2099-01-01")
    commitments.complete_commitment(conn, cid1)
    assert len(commitments.get_commitments(conn, "active")) == 1
    assert len(commitments.get_commitments(conn, "completed")) == 1


def test_overdue_commitments(conn):
    past = (_dt.date.today() - _dt.timedelta(days=5)).isoformat()
    commitments.create_commitment(conn, "late", past)
    commitments.create_commitment(conn, "future", "2099-01-01")
    overdue = commitments.overdue_commitments(conn)
    assert len(overdue) == 1
    assert overdue[0]["text"] == "late"


def test_overdue_excludes_completed(conn):
    past = (_dt.date.today() - _dt.timedelta(days=5)).isoformat()
    cid = commitments.create_commitment(conn, "late", past)
    commitments.complete_commitment(conn, cid)
    assert commitments.overdue_commitments(conn) == []


def test_empty_commitments(conn):
    assert commitments.get_commitments(conn) == []


def test_get_commitments_failed(conn):
    cid = commitments.create_commitment(conn, "x", "2099-01-01")
    commitments.fail_commitment(conn, cid)
    assert len(commitments.get_commitments(conn, "failed")) == 1
