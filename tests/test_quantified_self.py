"""Tests for sentinel.quantified_self."""
import pytest
from sentinel import quantified_self, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_get_daily_score_empty(conn):
    result = quantified_self.get_daily_score(conn)
    assert "score" in result
    assert "components" in result
    assert "weights" in result


def test_score_has_all_components(conn):
    result = quantified_self.get_daily_score(conn)
    for key in ["productivity", "wellness", "mood", "habits", "deep_work", "meditation"]:
        assert key in result["components"]


def test_weights_sum_to_one():
    total = sum(quantified_self.WEIGHTS.values())
    assert abs(total - 1.0) < 0.01


def test_weekly_aggregate(conn):
    result = quantified_self.weekly_aggregate(conn)
    assert "avg" in result
    assert "days" in result
    assert len(result["days"]) == 7


def test_metric_trend_empty(conn):
    trend = quantified_self.metric_trend(conn, "productivity")
    assert trend in ("improving", "declining", "stable")


def test_specific_date(conn):
    result = quantified_self.get_daily_score(conn, "2026-04-09")
    assert result["date"] == "2026-04-09"


def test_wellness_component_empty(conn):
    score = quantified_self._wellness_score(conn, "2026-04-09")
    assert score == 0


def test_mood_component_empty(conn):
    score = quantified_self._mood_score(conn, "2026-04-09")
    assert score == 0


def test_habits_component_empty(conn):
    score = quantified_self._habits_score(conn, "2026-04-09")
    assert score == 0


def test_deep_work_component_empty(conn):
    score = quantified_self._deep_work_score(conn, "2026-04-09")
    assert score == 0
