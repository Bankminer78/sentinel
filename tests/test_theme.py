"""Tests for sentinel.theme."""
import pytest
from sentinel import theme, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_list_themes():
    themes = theme.list_themes()
    assert len(themes) >= 3
    assert all("id" in t and "name" in t for t in themes)


def test_get_theme():
    t = theme.get_theme("dark")
    assert t is not None
    assert t["bg"]


def test_get_nonexistent_theme():
    assert theme.get_theme("nonexistent") is None


def test_set_current_theme(conn):
    assert theme.set_current_theme(conn, "light") is True
    assert theme.get_current_theme(conn) == "light"


def test_set_invalid_theme(conn):
    assert theme.set_current_theme(conn, "invalid") is False


def test_default_theme(conn):
    assert theme.get_current_theme(conn) == "dark"


def test_get_current_theme_data(conn):
    theme.set_current_theme(conn, "nord")
    data = theme.get_current_theme_data(conn)
    assert data["id"] == "nord"
    assert data["bg"]


def test_generate_css():
    css = theme.generate_css("dark")
    assert ":root" in css
    assert "--bg" in css


def test_theme_count():
    assert theme.theme_count() >= 5


def test_all_themes_have_required_keys():
    for t in theme.list_themes():
        for key in ["bg", "text", "primary", "secondary"]:
            assert key in t
