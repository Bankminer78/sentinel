"""Tests for sentinel.weight_tracker."""
import pytest
from sentinel import weight_tracker as wt, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_log_weight(conn):
    lid = wt.log_weight(conn, 75.5, "After workout")
    assert lid > 0


def test_get_weights(conn):
    wt.log_weight(conn, 75)
    assert len(wt.get_weights(conn)) == 1


def test_current_weight(conn):
    wt.log_weight(conn, 75.5)
    assert wt.current_weight(conn) == 75.5


def test_current_weight_empty(conn):
    assert wt.current_weight(conn) == 0


def test_set_height(conn):
    wt.set_height(conn, 180)
    cfg = wt.get_config(conn)
    assert cfg["height_cm"] == 180


def test_set_target(conn):
    wt.set_height(conn, 180)
    wt.set_target(conn, 70)
    cfg = wt.get_config(conn)
    assert cfg["target_kg"] == 70


def test_bmi(conn):
    wt.set_height(conn, 180)  # 1.8m
    wt.log_weight(conn, 81)  # 81 / 1.8^2 = 25.0
    assert wt.bmi(conn) == 25.0


def test_bmi_no_data(conn):
    assert wt.bmi(conn) == 0


def test_trend_stable(conn):
    assert wt.trend(conn) == "stable"


def test_progress_no_target(conn):
    prog = wt.progress_to_target(conn)
    assert prog["target"] == 0


def test_avg_weekly(conn):
    wt.log_weight(conn, 80)
    assert wt.avg_weekly(conn) == 80.0


def test_delete_entry(conn):
    wt.log_weight(conn, 75)
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    wt.delete_entry(conn, today)
    assert wt.get_weights(conn) == []
