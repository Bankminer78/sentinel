"""Tests for sentinel.dashboard — single-page HTML dashboard."""

import pytest

from sentinel import dashboard


class TestDashboardHTML:
    def test_returns_string(self):
        html = dashboard.get_dashboard_html()
        assert isinstance(html, str)
        assert len(html) > 100

    def test_has_doctype(self):
        assert dashboard.get_dashboard_html().startswith("<!DOCTYPE html>")

    def test_has_title(self):
        assert "<title>Sentinel Dashboard</title>" in dashboard.get_dashboard_html()

    def test_has_all_tabs(self):
        html = dashboard.get_dashboard_html()
        for tab in ["Overview", "Rules", "Stats", "Goals", "Habits", "Challenges"]:
            assert tab in html

    def test_dark_theme_colors(self):
        html = dashboard.get_dashboard_html()
        assert "#09090b" in html or "#18181b" in html
        assert "#ef4444" in html  # red accent

    def test_fetches_api_endpoints(self):
        html = dashboard.get_dashboard_html()
        for path in ["/status", "/stats", "/rules", "/goals"]:
            assert path in html

    def test_has_script(self):
        html = dashboard.get_dashboard_html()
        assert "<script>" in html and "</script>" in html

    def test_has_panels(self):
        html = dashboard.get_dashboard_html()
        for pid in ["panel-overview", "panel-rules", "panel-stats",
                    "panel-goals", "panel-habits", "panel-challenges"]:
            assert pid in html


class TestStatsFragment:
    def test_renders_score(self):
        out = dashboard.render_stats_fragment({"score": 88, "total_activities": 10, "blocked_count": 2})
        assert "88/100" in out
        assert "10" in out
        assert "2" in out

    def test_defaults_to_zero(self):
        out = dashboard.render_stats_fragment({})
        assert "0/100" in out


class TestServed:
    def test_served_at_root(self):
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        from sentinel.server import app
        from sentinel import blocker, monitor
        with patch.object(blocker, "_sync_hosts"), \
             patch("sentinel.server.startup"), \
             patch.object(monitor, "start"):
            with TestClient(app) as client:
                r = client.get("/")
                assert r.status_code == 200
                assert "Sentinel Dashboard" in r.text
