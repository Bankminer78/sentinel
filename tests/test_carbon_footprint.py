"""Tests for sentinel.carbon_footprint."""
import pytest
from sentinel import carbon_footprint as cf, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_log_activity(conn):
    lid = cf.log_activity(conn, "car_km", 100)
    assert lid > 0


def test_get_log(conn):
    cf.log_activity(conn, "car_km", 100)
    cf.log_activity(conn, "flight_short", 500)
    assert len(cf.get_log(conn)) == 2


def test_total_kg(conn):
    cf.log_activity(conn, "car_km", 100)  # 0.18 * 100 = 18
    assert cf.total_kg(conn) == 18.0


def test_by_activity(conn):
    cf.log_activity(conn, "car_km", 100)
    cf.log_activity(conn, "flight_short", 500)
    by_act = cf.by_activity(conn)
    assert "car_km" in by_act
    assert "flight_short" in by_act


def test_list_activities():
    activities = cf.list_activities()
    assert "car_km" in activities
    assert "beef_meal" in activities


def test_get_factor():
    assert cf.get_factor("car_km") == 0.18
    assert cf.get_factor("unknown") == 0


def test_daily_average(conn):
    cf.log_activity(conn, "car_km", 100)  # 18 kg
    avg = cf.daily_average(conn, days=30)
    assert avg == 0.6  # 18/30


def test_delete_log_entry(conn):
    lid = cf.log_activity(conn, "car_km", 50)
    cf.delete_log_entry(conn, lid)
    assert cf.get_log(conn) == []


def test_biggest_sources(conn):
    cf.log_activity(conn, "car_km", 100)
    cf.log_activity(conn, "flight_short", 1000)
    big = cf.biggest_sources(conn, limit=2)
    assert big[0]["activity"] == "flight_short"


def test_set_get_target(conn):
    cf.set_target(conn, 100)
    assert cf.get_target(conn) == 100.0


def test_unknown_activity_zero(conn):
    cf.log_activity(conn, "unknown", 1000)
    assert cf.total_kg(conn) == 0
