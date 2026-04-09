"""Tests for sentinel.distraction_log."""
import pytest
from sentinel import distraction_log as dl, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_log_distraction(conn):
    did = dl.log_distraction(conn, "phone", "Checked Twitter", 300, "boredom")
    assert did > 0


def test_get_distractions(conn):
    dl.log_distraction(conn, "phone", "", 60)
    dl.log_distraction(conn, "social_media", "", 120)
    assert len(dl.get_distractions(conn)) == 2


def test_delete_distraction(conn):
    did = dl.log_distraction(conn, "email")
    dl.delete_distraction(conn, did)
    assert dl.get_distractions(conn) == []


def test_count_by_type(conn):
    dl.log_distraction(conn, "phone")
    dl.log_distraction(conn, "phone")
    dl.log_distraction(conn, "email")
    counts = dl.count_by_type(conn)
    assert counts["phone"] == 2
    assert counts["email"] == 1


def test_total_distracted_seconds(conn):
    dl.log_distraction(conn, "phone", duration_s=60)
    dl.log_distraction(conn, "phone", duration_s=120)
    assert dl.total_distracted_seconds(conn) == 180


def test_triggers_ranked(conn):
    dl.log_distraction(conn, "phone", triggered_by="boredom")
    dl.log_distraction(conn, "phone", triggered_by="boredom")
    dl.log_distraction(conn, "email", triggered_by="anxiety")
    triggers = dl.triggers_ranked(conn)
    assert triggers[0]["trigger"] == "boredom"
    assert triggers[0]["count"] == 2


def test_by_hour(conn):
    dl.log_distraction(conn, "phone")
    by_hour = dl.distractions_by_hour(conn)
    assert len(by_hour) >= 1


def test_get_types():
    types = dl.get_types()
    assert "phone" in types
    assert "internet" in types
    assert len(types) >= 10


def test_empty(conn):
    assert dl.get_distractions(conn) == []
    assert dl.count_by_type(conn) == {}
    assert dl.triggers_ranked(conn) == []


def test_total_empty(conn):
    assert dl.total_distracted_seconds(conn) == 0
