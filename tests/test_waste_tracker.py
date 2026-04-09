"""Tests for sentinel.waste_tracker."""
import pytest
from sentinel import waste_tracker as wt, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_log_waste(conn):
    lid = wt.log_waste(conn, "Scrolling Reddit", 30, "social", 8)
    assert lid > 0


def test_total_today(conn):
    wt.log_waste(conn, "A", 30)
    wt.log_waste(conn, "B", 15)
    assert wt.total_wasted_today(conn) == 45


def test_total_week(conn):
    wt.log_waste(conn, "A", 60)
    assert wt.total_wasted_week(conn) >= 60


def test_top_wastes(conn):
    wt.log_waste(conn, "Reddit", 30)
    wt.log_waste(conn, "Reddit", 20)
    wt.log_waste(conn, "YouTube", 10)
    top = wt.top_wastes(conn)
    assert top[0]["activity"] == "Reddit"
    assert top[0]["total"] == 50


def test_by_category(conn):
    wt.log_waste(conn, "A", 10, "social")
    wt.log_waste(conn, "B", 20, "entertainment")
    by_cat = wt.by_category(conn)
    assert "social" in by_cat
    assert "entertainment" in by_cat


def test_avg_regret(conn):
    wt.log_waste(conn, "A", 10, regret_level=8)
    wt.log_waste(conn, "B", 10, regret_level=4)
    assert wt.avg_regret(conn) == 6.0


def test_high_regret_items(conn):
    wt.log_waste(conn, "Bad", 30, regret_level=9)
    wt.log_waste(conn, "Ok", 10, regret_level=4)
    high = wt.high_regret_items(conn)
    assert len(high) == 1


def test_delete_entry(conn):
    lid = wt.log_waste(conn, "Delete", 10)
    wt.delete_entry(conn, lid)
    assert wt.total_wasted_today(conn) == 0


def test_get_log(conn):
    wt.log_waste(conn, "A", 10)
    wt.log_waste(conn, "B", 20)
    log = wt.get_log(conn)
    assert len(log) == 2


def test_trend_empty(conn):
    assert wt.waste_trend(conn) == "stable"


def test_empty(conn):
    assert wt.top_wastes(conn) == []
    assert wt.high_regret_items(conn) == []
