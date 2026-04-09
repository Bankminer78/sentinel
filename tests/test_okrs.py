"""Tests for sentinel.okrs."""
import pytest
from sentinel import okrs, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_current_quarter():
    q = okrs.current_quarter()
    assert "-Q" in q


def test_add_objective(conn):
    oid = okrs.add_objective(conn, "Ship the MVP")
    assert oid > 0


def test_get_objectives(conn):
    okrs.add_objective(conn, "Obj 1")
    okrs.add_objective(conn, "Obj 2")
    objs = okrs.get_objectives(conn)
    assert len(objs) == 2


def test_get_objectives_by_quarter(conn):
    okrs.add_objective(conn, "Q1 obj", "2026-Q1")
    okrs.add_objective(conn, "Q2 obj", "2026-Q2")
    q1 = okrs.get_objectives(conn, "2026-Q1")
    assert len(q1) == 1


def test_delete_objective(conn):
    oid = okrs.add_objective(conn, "To delete")
    okrs.delete_objective(conn, oid)
    assert okrs.get_objectives(conn) == []


def test_add_key_result(conn):
    oid = okrs.add_objective(conn, "Obj")
    krid = okrs.add_key_result(conn, oid, "KR1", 100, "users")
    assert krid > 0


def test_get_key_results(conn):
    oid = okrs.add_objective(conn, "Obj")
    okrs.add_key_result(conn, oid, "KR1", 100)
    okrs.add_key_result(conn, oid, "KR2", 50)
    krs = okrs.get_key_results(conn, oid)
    assert len(krs) == 2


def test_update_key_result(conn):
    oid = okrs.add_objective(conn, "Obj")
    krid = okrs.add_key_result(conn, oid, "KR", 100)
    okrs.update_key_result(conn, krid, 75)
    krs = okrs.get_key_results(conn, oid)
    assert krs[0]["current"] == 75


def test_objective_progress(conn):
    oid = okrs.add_objective(conn, "Obj")
    k1 = okrs.add_key_result(conn, oid, "KR1", 100)
    k2 = okrs.add_key_result(conn, oid, "KR2", 50)
    okrs.update_key_result(conn, k1, 50)
    okrs.update_key_result(conn, k2, 50)
    progress = okrs.get_objective_progress(conn, oid)
    # k1: 50/100 = 50%, k2: 50/50 = 100%, avg = 75%
    assert progress["percent"] == 75.0


def test_progress_no_krs(conn):
    oid = okrs.add_objective(conn, "Obj")
    progress = okrs.get_objective_progress(conn, oid)
    assert progress["percent"] == 0


def test_progress_over_100(conn):
    oid = okrs.add_objective(conn, "Obj")
    krid = okrs.add_key_result(conn, oid, "KR", 100)
    okrs.update_key_result(conn, krid, 200)  # Overshoot
    progress = okrs.get_objective_progress(conn, oid)
    assert progress["percent"] == 100  # Capped


def test_quarterly_summary(conn):
    okrs.add_objective(conn, "Obj1", "2026-Q2")
    okrs.add_objective(conn, "Obj2", "2026-Q2")
    summary = okrs.quarterly_summary(conn, "2026-Q2")
    assert len(summary["objectives"]) == 2
