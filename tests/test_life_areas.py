"""Tests for sentinel.life_areas."""
import pytest
from sentinel import life_areas, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_init_defaults(conn):
    life_areas.init_default_areas(conn)
    areas = life_areas.get_areas(conn)
    assert len(areas) >= 8


def test_add_custom_area(conn):
    aid = life_areas.add_area(conn, "Hobbies", "🎨")
    assert aid >= 0


def test_update_score(conn):
    life_areas.init_default_areas(conn)
    areas = life_areas.get_areas(conn)
    health = next(a for a in areas if a["name"] == "Health")
    life_areas.update_score(conn, health["id"], 8, "Feeling great")
    updated = life_areas.get_areas(conn)
    assert next(a for a in updated if a["name"] == "Health")["current_score"] == 8


def test_set_target(conn):
    life_areas.init_default_areas(conn)
    areas = life_areas.get_areas(conn)
    life_areas.set_target(conn, areas[0]["id"], 9)
    updated = life_areas.get_areas(conn)
    assert updated[0]["target_score"] == 9


def test_get_history(conn):
    life_areas.init_default_areas(conn)
    areas = life_areas.get_areas(conn)
    life_areas.update_score(conn, areas[0]["id"], 7)
    history = life_areas.get_area_history(conn, areas[0]["id"])
    assert len(history) == 1


def test_balance_score_empty(conn):
    bs = life_areas.balance_score(conn)
    assert bs["score"] == 0


def test_balance_score_with_data(conn):
    life_areas.init_default_areas(conn)
    bs = life_areas.balance_score(conn)
    assert bs["score"] > 0
    assert bs["weakest"]
    assert bs["strongest"]


def test_imbalance_alert(conn):
    life_areas.init_default_areas(conn)
    areas = life_areas.get_areas(conn)
    life_areas.update_score(conn, areas[0]["id"], 2)
    alerts = life_areas.imbalance_alert(conn, threshold=3)
    assert len(alerts) >= 1


def test_delete_area(conn):
    aid = life_areas.add_area(conn, "Test")
    life_areas.delete_area(conn, aid)
    areas = life_areas.get_areas(conn)
    assert not any(a["id"] == aid for a in areas)


def test_default_areas_have_icons(conn):
    life_areas.init_default_areas(conn)
    areas = life_areas.get_areas(conn)
    for a in areas:
        assert a["icon"]
