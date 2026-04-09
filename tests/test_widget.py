"""Tests for sentinel.widget."""
import pytest
from sentinel import widget, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_small_widget(conn):
    data = widget.small_widget_data(conn)
    assert data["size"] == "small"
    assert "score" in data


def test_medium_widget(conn):
    data = widget.medium_widget_data(conn)
    assert data["size"] == "medium"
    assert "top_distractions" in data


def test_large_widget(conn):
    data = widget.large_widget_data(conn)
    assert data["size"] == "large"
    assert "rules_count" in data


def test_lockscreen_widget(conn):
    data = widget.lockscreen_widget_data(conn)
    assert data["size"] == "lockscreen"
    assert "text" in data


def test_dynamic_island_no_pomodoro(conn):
    data = widget.dynamic_island_data(conn)
    assert data["active"] is False


def test_refresh_interval():
    assert widget.refresh_interval_seconds() > 0


def test_widget_has_color(conn):
    data = widget.small_widget_data(conn)
    assert "color" in data
