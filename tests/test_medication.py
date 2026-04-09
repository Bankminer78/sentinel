"""Tests for sentinel.medication."""
import pytest
from sentinel import medication, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_medication(conn):
    mid = medication.add_medication(conn, "Vitamin D", "1000 IU", "daily", 1)
    assert mid > 0


def test_get_medications(conn):
    medication.add_medication(conn, "Med1")
    medication.add_medication(conn, "Med2")
    assert len(medication.get_medications(conn)) == 2


def test_deactivate(conn):
    mid = medication.add_medication(conn, "Test")
    medication.deactivate_medication(conn, mid)
    assert len(medication.get_medications(conn, active_only=True)) == 0
    assert len(medication.get_medications(conn, active_only=False)) == 1


def test_log_taken(conn):
    mid = medication.add_medication(conn, "Test")
    lid = medication.log_taken(conn, mid)
    assert lid > 0


def test_taken_today(conn):
    mid = medication.add_medication(conn, "Test")
    medication.log_taken(conn, mid)
    medication.log_taken(conn, mid)
    assert medication.taken_today(conn, mid) == 2


def test_adherence_rate(conn):
    mid = medication.add_medication(conn, "Test", times_per_day=1)
    medication.log_taken(conn, mid)
    # For 30 days expected, 1 taken = 3.3%
    rate = medication.adherence_rate(conn, mid)
    assert rate > 0


def test_missed_doses_today(conn):
    medication.add_medication(conn, "Test", times_per_day=3)
    missed = medication.missed_doses_today(conn)
    assert len(missed) == 1
    assert missed[0]["missing"] == 3


def test_delete_medication(conn):
    mid = medication.add_medication(conn, "Test")
    medication.delete_medication(conn, mid)
    assert len(medication.get_medications(conn, active_only=False)) == 0


def test_medication_streak(conn):
    mid = medication.add_medication(conn, "Test", times_per_day=1)
    medication.log_taken(conn, mid)
    assert medication.medication_streak(conn, mid) >= 1


def test_nonexistent_adherence(conn):
    assert medication.adherence_rate(conn, 999) == 0
