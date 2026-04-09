"""Tests for sentinel.webui."""
import pytest
from sentinel import webui


def test_render_page_wraps_html():
    html = webui.render_page("Test", "<p>body</p>")
    assert "<!DOCTYPE html>" in html
    assert "<title>Test</title>" in html
    assert "<p>body</p>" in html


def test_render_page_has_dark_theme():
    html = webui.render_page("T", "")
    assert "#09090b" in html  # dark bg
    assert "#ef4444" in html  # sentinel red


def test_render_page_has_nav():
    html = webui.render_page("T", "")
    assert "/ui/rules" in html
    assert "/ui/stats" in html


def test_render_page_escapes_title():
    html = webui.render_page("<script>", "")
    assert "<title><script></title>" not in html
    assert "&lt;script&gt;" in html


def test_render_rules_page_empty():
    html = webui.render_rules_page_html([])
    assert "No rules" in html
    assert "<!DOCTYPE html>" in html


def test_render_rules_page_with_rules():
    rules = [
        {"id": 1, "text": "block youtube", "active": 1},
        {"id": 2, "text": "limit reddit", "active": 0},
    ]
    html = webui.render_rules_page_html(rules)
    assert "block youtube" in html
    assert "limit reddit" in html
    assert "active" in html
    assert "off" in html


def test_render_rules_page_escapes():
    rules = [{"id": 1, "text": "<script>x</script>", "active": 1}]
    html = webui.render_rules_page_html(rules)
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_stats_page_empty():
    html = webui.render_stats_page_html({})
    assert "No data" in html


def test_render_stats_page_with_data():
    html = webui.render_stats_page_html({"blocks_today": 5, "focus_minutes": 120})
    assert "blocks_today" in html
    assert "5" in html
    assert "focus_minutes" in html
    assert "120" in html


def test_render_achievements_page_unlocked():
    html = webui.render_achievements_page_html(
        [{"name": "First Block"}], [{"name": "Master"}])
    assert "First Block" in html
    assert "Master" in html
    assert "unlocked" in html
    assert "locked" in html


def test_render_achievements_page_empty():
    html = webui.render_achievements_page_html([], [])
    assert "None yet" in html
    assert "None" in html


def test_render_habits_page_with_habits():
    habits = [{"name": "meditate", "frequency": "daily"},
              {"name": "workout", "frequency": "weekly"}]
    html = webui.render_habits_page_html(habits)
    assert "meditate" in html
    assert "workout" in html
    assert "daily" in html
    assert "weekly" in html


def test_render_habits_page_empty():
    html = webui.render_habits_page_html([])
    assert "No habits" in html


def test_render_chat_page_has_form():
    html = webui.render_chat_page_html()
    assert "<textarea" in html
    assert "ask()" in html
    assert "/chat" in html


def test_render_chat_page_is_complete_html():
    html = webui.render_chat_page_html()
    assert "<!DOCTYPE html>" in html
    assert "</html>" in html
