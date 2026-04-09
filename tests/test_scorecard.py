"""Tests for sentinel.scorecard."""
import pytest
from sentinel import scorecard as sc, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_init_defaults(conn):
    sc.init_defaults(conn)
    metrics = sc.get_metrics(conn)
    assert len(metrics) >= 5


def test_add_metric(conn):
    mid = sc.add_metric(conn, "custom_metric", weight=2.0)
    assert mid >= 0


def test_get_metrics(conn):
    sc.add_metric(conn, "metric1")
    sc.add_metric(conn, "metric2")
    assert len(sc.get_metrics(conn)) == 2


def test_record_score(conn):
    sc.add_metric(conn, "focus")
    sid = sc.record_score(conn, "focus", 8)
    assert sid > 0


def test_get_day_scores(conn):
    sc.add_metric(conn, "focus")
    sc.add_metric(conn, "energy")
    sc.record_score(conn, "focus", 8)
    sc.record_score(conn, "energy", 7)
    scores = sc.get_day_scores(conn)
    assert scores["focus"] == 8
    assert scores["energy"] == 7


def test_overall_score_empty(conn):
    assert sc.overall_score(conn) == 0


def test_overall_score(conn):
    sc.add_metric(conn, "focus")
    sc.record_score(conn, "focus", 8)
    score = sc.overall_score(conn)
    assert score == 80.0  # 8/10 * 100


def test_avg_metric(conn):
    sc.add_metric(conn, "focus")
    sc.record_score(conn, "focus", 8)
    assert sc.avg_metric(conn, "focus") == 8.0


def test_week_overview(conn):
    sc.add_metric(conn, "focus")
    sc.record_score(conn, "focus", 8)
    overview = sc.week_overview(conn)
    assert len(overview) == 7


def test_delete_metric(conn):
    sc.add_metric(conn, "temp")
    sc.delete_metric(conn, "temp")
    metrics = sc.get_metrics(conn)
    assert not any(m["name"] == "temp" for m in metrics)


def test_trend_stable(conn):
    sc.add_metric(conn, "focus")
    assert sc.trend(conn, "focus") == "stable"


def test_update_score(conn):
    sc.add_metric(conn, "focus")
    sc.record_score(conn, "focus", 5)
    sc.record_score(conn, "focus", 8)  # Should replace
    assert sc.get_day_scores(conn)["focus"] == 8
