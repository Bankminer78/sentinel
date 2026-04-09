"""Tests for sentinel.wellness."""
import pytest
from sentinel import wellness, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_log_water(conn):
    wellness.log_water(conn, 16)
    totals = wellness.daily_totals(conn)
    assert totals["water_oz"] == 16


def test_log_multiple_water(conn):
    wellness.log_water(conn, 8)
    wellness.log_water(conn, 16)
    assert wellness.daily_totals(conn)["water_oz"] == 24


def test_log_eye_break(conn):
    wellness.log_eye_break(conn)
    wellness.log_eye_break(conn)
    assert wellness.daily_totals(conn)["eye_breaks"] == 2


def test_log_posture(conn):
    wellness.log_posture_check(conn, 8)
    totals = wellness.daily_totals(conn)
    assert totals["avg_posture"] == 8.0


def test_log_energy(conn):
    wellness.log_energy(conn, 7)
    totals = wellness.daily_totals(conn)
    assert totals["avg_energy"] == 7.0


def test_avg_posture(conn):
    wellness.log_posture_check(conn, 6)
    wellness.log_posture_check(conn, 8)
    assert wellness.daily_totals(conn)["avg_posture"] == 7.0


def test_empty_daily_totals(conn):
    t = wellness.daily_totals(conn)
    assert t["water_oz"] == 0
    assert t["eye_breaks"] == 0


def test_set_reminder(conn):
    rid = wellness.set_reminder(conn, "water", 60)
    assert rid > 0


def test_get_reminders(conn):
    wellness.set_reminder(conn, "water", 60)
    wellness.set_reminder(conn, "posture", 30)
    assert len(wellness.get_reminders(conn)) == 2


def test_delete_reminder(conn):
    rid = wellness.set_reminder(conn, "eye", 20)
    wellness.delete_reminder(conn, rid)
    assert wellness.get_reminders(conn) == []


def test_reminders_due(conn):
    wellness.set_reminder(conn, "water", 60)
    due = wellness.reminders_due(conn)
    assert len(due) == 1  # Newly created, never triggered


def test_mark_reminder_triggered(conn):
    rid = wellness.set_reminder(conn, "water", 60)
    wellness.mark_reminder_triggered(conn, rid)
    due = wellness.reminders_due(conn)
    assert len(due) == 0  # Just triggered
