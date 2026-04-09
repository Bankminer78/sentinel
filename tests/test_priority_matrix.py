"""Tests for sentinel.priority_matrix."""
import pytest
from sentinel import priority_matrix as pm, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_task(conn):
    tid = pm.add_task(conn, "Important task", urgent=True, important=True)
    assert tid > 0


def test_quadrant_q1(conn):
    tid = pm.add_task(conn, "Test", urgent=True, important=True)
    assert pm.get_quadrant(tid, conn) == "Q1"


def test_quadrant_q2(conn):
    tid = pm.add_task(conn, "Test", urgent=False, important=True)
    assert pm.get_quadrant(tid, conn) == "Q2"


def test_quadrant_q3(conn):
    tid = pm.add_task(conn, "Test", urgent=True, important=False)
    assert pm.get_quadrant(tid, conn) == "Q3"


def test_quadrant_q4(conn):
    tid = pm.add_task(conn, "Test", urgent=False, important=False)
    assert pm.get_quadrant(tid, conn) == "Q4"


def test_get_tasks_in_quadrant(conn):
    pm.add_task(conn, "T1", urgent=True, important=True)
    pm.add_task(conn, "T2", urgent=True, important=True)
    q1_tasks = pm.get_tasks_in_quadrant(conn, "Q1")
    assert len(q1_tasks) == 2


def test_get_all_tasks(conn):
    pm.add_task(conn, "T1", urgent=True, important=True)
    pm.add_task(conn, "T2", urgent=False, important=True)
    all_tasks = pm.get_all_tasks(conn)
    assert len(all_tasks["Q1"]) == 1
    assert len(all_tasks["Q2"]) == 1


def test_complete_task(conn):
    tid = pm.add_task(conn, "Test", urgent=True, important=True)
    pm.complete_task(conn, tid)
    assert len(pm.get_tasks_in_quadrant(conn, "Q1")) == 0


def test_delete_task(conn):
    tid = pm.add_task(conn, "Test")
    pm.delete_task(conn, tid)
    assert pm.q1_count(conn) == 0


def test_move_task(conn):
    tid = pm.add_task(conn, "Test", urgent=False, important=False)
    pm.move_task(conn, tid, urgent=True, important=True)
    assert pm.get_quadrant(tid, conn) == "Q1"


def test_overwhelmed(conn):
    for i in range(6):
        pm.add_task(conn, f"T{i}", urgent=True, important=True)
    assert pm.overwhelmed(conn) is True


def test_advice(conn):
    advice = pm.advice(conn)
    assert advice  # Returns some advice string


def test_list_quadrants():
    quadrants = pm.list_quadrants()
    assert len(quadrants) == 4
