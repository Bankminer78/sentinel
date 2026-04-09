"""Tests for sentinel.user_journey."""
import pytest
from sentinel import user_journey, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_record_milestone(conn):
    mid = user_journey.record_milestone(conn, "First rule created")
    assert mid > 0


def test_get_milestones(conn):
    user_journey.record_milestone(conn, "Milestone 1")
    user_journey.record_milestone(conn, "Milestone 2")
    assert len(user_journey.get_milestones(conn)) == 2


def test_get_milestones_by_category(conn):
    user_journey.record_milestone(conn, "Rule created", category="rule")
    user_journey.record_milestone(conn, "Goal set", category="goal")
    rules = user_journey.get_milestones(conn, category="rule")
    assert len(rules) == 1


def test_delete_milestone(conn):
    mid = user_journey.record_milestone(conn, "Test")
    user_journey.delete_milestone(conn, mid)
    assert user_journey.get_milestones(conn) == []


def test_timeline_empty(conn):
    timeline = user_journey.journey_timeline(conn)
    assert isinstance(timeline, list)


def test_timeline_with_data(conn):
    user_journey.record_milestone(conn, "Test milestone")
    timeline = user_journey.journey_timeline(conn)
    assert len(timeline) >= 1


def test_growth_chart(conn):
    chart = user_journey.growth_chart(conn, days=7)
    assert len(chart) == 7
    assert all("date" in d and "score" in d for d in chart)


def test_streak_record(conn):
    streaks = user_journey.streak_record(conn)
    assert isinstance(streaks, dict)


def test_growth_summary(conn):
    user_journey.record_milestone(conn, "Test")
    summary = user_journey.growth_summary(conn)
    assert summary["milestones"] == 1


def test_empty_milestones(conn):
    assert user_journey.get_milestones(conn) == []
