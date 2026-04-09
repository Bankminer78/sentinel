"""Tests for sentinel.focus_stones."""
import pytest
from sentinel import focus_stones as fs, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_earn_stone_pebble(conn):
    stone = fs.earn_stone(conn, 10)
    assert stone["id"] == "pebble"


def test_earn_stone_mountain(conn):
    stone = fs.earn_stone(conn, 45)
    assert stone["id"] == "mountain"


def test_earn_stone_diamond(conn):
    stone = fs.earn_stone(conn, 200)
    assert stone["id"] == "diamond"


def test_earn_stone_too_short(conn):
    assert fs.earn_stone(conn, 3) is None


def test_get_collection(conn):
    fs.earn_stone(conn, 10)
    fs.earn_stone(conn, 20)
    collection = fs.get_collection(conn)
    assert collection["pebble"]["count"] == 1
    assert collection["river"]["count"] == 1


def test_total_stones(conn):
    fs.earn_stone(conn, 10)
    fs.earn_stone(conn, 20)
    assert fs.total_stones(conn) == 2


def test_total_value(conn):
    fs.earn_stone(conn, 10)
    fs.earn_stone(conn, 30)
    assert fs.total_value(conn) == 40


def test_rarest_stone_empty(conn):
    assert fs.rarest_stone(conn) is None


def test_list_stone_types():
    types = fs.list_stone_types()
    assert len(types) >= 5


def test_stone_info():
    pebble = fs.stone_info("pebble")
    assert pebble["cost_minutes"] == 5


def test_stone_info_invalid():
    assert fs.stone_info("invalid") is None


def test_recent_stones(conn):
    fs.earn_stone(conn, 10)
    assert len(fs.recent_stones(conn)) == 1


def test_stones_today(conn):
    fs.earn_stone(conn, 10)
    assert fs.stones_earned_today(conn) == 1


def test_stones_this_week(conn):
    fs.earn_stone(conn, 10)
    assert fs.stones_this_week(conn) >= 1
