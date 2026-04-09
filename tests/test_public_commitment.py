"""Tests for sentinel.public_commitment."""
import pytest
from sentinel import public_commitment as pc, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_commitment(conn):
    cid = pc.add_commitment(conn, "Run a marathon", "2026-12-31", "twitter", "$100")
    assert cid > 0


def test_get_commitments(conn):
    pc.add_commitment(conn, "C1", "2026-12-31")
    pc.add_commitment(conn, "C2", "2026-12-31")
    assert len(pc.get_commitments(conn)) == 2


def test_mark_completed(conn):
    cid = pc.add_commitment(conn, "Test", "2026-04-09")
    pc.mark_completed(conn, cid)
    assert len(pc.completed_commitments(conn)) == 1


def test_mark_failed(conn):
    cid = pc.add_commitment(conn, "Test", "2026-04-09")
    pc.mark_failed(conn, cid)
    assert len(pc.failed_commitments(conn)) == 1


def test_delete(conn):
    cid = pc.add_commitment(conn, "Del", "2026-04-09")
    pc.delete_commitment(conn, cid)
    assert pc.total_count(conn) == 0


def test_overdue(conn):
    pc.add_commitment(conn, "Past deadline", "1999-01-01")
    overdue = pc.overdue(conn)
    assert len(overdue) == 1


def test_pending(conn):
    pc.add_commitment(conn, "Pending", "2999-12-31")
    assert len(pc.pending_commitments(conn)) == 1


def test_commitment_rate_empty(conn):
    assert pc.commitment_rate(conn) == 0


def test_commitment_rate(conn):
    cid1 = pc.add_commitment(conn, "C1", "2026-04-09")
    cid2 = pc.add_commitment(conn, "C2", "2026-04-09")
    pc.mark_completed(conn, cid1)
    pc.mark_failed(conn, cid2)
    assert pc.commitment_rate(conn) == 50.0


def test_format_for_twitter():
    c = {"text": "Run 5k", "deadline": "2026-12-31", "stakes": "$100"}
    t = pc.format_for_twitter(c)
    assert "Run 5k" in t
    assert len(t) <= 280


def test_format_for_linkedin():
    c = {"text": "Run 5k", "deadline": "2026-12-31"}
    l = pc.format_for_linkedin(c)
    assert "Run 5k" in l


def test_total_count(conn):
    pc.add_commitment(conn, "C1", "2026-04-09")
    pc.add_commitment(conn, "C2", "2026-04-09")
    assert pc.total_count(conn) == 2
