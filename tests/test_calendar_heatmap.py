"""Tests for sentinel.calendar_heatmap."""
import pytest
from sentinel import calendar_heatmap as ch, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_activity_heatmap_empty(conn):
    assert ch.activity_heatmap_data(conn) == {}


def test_activity_heatmap_with_data(conn):
    db.log_activity(conn, "App", "T", "", "test.com")
    data = ch.activity_heatmap_data(conn)
    assert len(data) >= 1


def test_score_heatmap_data(conn):
    data = ch.score_heatmap_data(conn, days=7)
    assert len(data) == 7


def test_render_heatmap_ascii_empty():
    assert ch.render_heatmap_ascii({}) == "(no data)"


def test_render_heatmap_ascii():
    data = {"2026-04-09": 5, "2026-04-08": 3}
    result = ch.render_heatmap_ascii(data)
    assert "Mon" in result or len(result) > 0


def test_render_html_empty():
    html = ch.render_html_heatmap({}, "Test")
    assert "no data" in html.lower()


def test_render_html_with_data():
    data = {"2026-04-09": 5}
    html = ch.render_html_heatmap(data)
    assert "heatmap" in html


def test_stats_empty():
    stats = ch.stats_for_heatmap({})
    assert stats["total"] == 0


def test_stats_with_data():
    data = {"2026-04-09": 5, "2026-04-08": 3, "2026-04-07": 0}
    stats = ch.stats_for_heatmap(data)
    assert stats["total"] == 8
    assert stats["days_active"] == 2
