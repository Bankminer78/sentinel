"""Tests for sentinel.achievements."""
import pytest
from sentinel import achievements, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_unlock_first_day(conn):
    assert achievements.unlock(conn, "first_day") is True


def test_unlock_invalid(conn):
    assert achievements.unlock(conn, "nonexistent") is False


def test_unlock_twice(conn):
    achievements.unlock(conn, "first_day")
    assert achievements.unlock(conn, "first_day") is False  # Already unlocked


def test_is_unlocked_false(conn):
    assert achievements.is_unlocked(conn, "first_day") is False


def test_is_unlocked_true(conn):
    achievements.unlock(conn, "first_day")
    assert achievements.is_unlocked(conn, "first_day") is True


def test_get_unlocked_empty(conn):
    assert achievements.get_unlocked(conn) == []


def test_get_unlocked_with_data(conn):
    achievements.unlock(conn, "first_day")
    achievements.unlock(conn, "week_streak")
    result = achievements.get_unlocked(conn)
    assert len(result) == 2
    ids = [r["id"] for r in result]
    assert "first_day" in ids
    assert "week_streak" in ids


def test_get_locked(conn):
    achievements.unlock(conn, "first_day")
    locked = achievements.get_locked(conn)
    ids = [l["id"] for l in locked]
    assert "first_day" not in ids
    assert "week_streak" in ids


def test_get_all_achievements():
    all_a = achievements.get_all_achievements()
    assert len(all_a) >= 10
    assert any(a["id"] == "first_day" for a in all_a)


def test_unlocked_has_timestamps(conn):
    achievements.unlock(conn, "first_day")
    result = achievements.get_unlocked(conn)
    assert "unlocked_at" in result[0]
    assert result[0]["unlocked_at"] > 0


def test_check_achievements_no_data(conn):
    newly = achievements.check_achievements(conn)
    assert isinstance(newly, list)


def test_check_achievements_rule_maker(conn):
    for i in range(10):
        db.add_rule(conn, f"Rule {i}")
    newly = achievements.check_achievements(conn)
    assert "rule_maker" in newly
    assert achievements.is_unlocked(conn, "rule_maker")


def test_check_achievements_blocker(conn):
    for i in range(100):
        db.log_activity(conn, "App", "T", "", "test.com", "block")
    newly = achievements.check_achievements(conn)
    assert "blocker" in newly


def test_check_achievements_idempotent(conn):
    db.add_rule(conn, "Test rule")
    achievements.check_achievements(conn)
    newly2 = achievements.check_achievements(conn)
    assert "first_day" not in newly2  # Already unlocked


def test_achievement_has_name_and_desc():
    for a in achievements.get_all_achievements():
        assert "name" in a
        assert "desc" in a
        assert "id" in a
