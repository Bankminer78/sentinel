"""Tests for sentinel.monitor — Activity monitoring (module-level functions)."""

import pytest

from sentinel import monitor
from sentinel.monitor import _extract_domain


# ---------------------------------------------------------------------------
# _extract_domain
# ---------------------------------------------------------------------------


class TestExtractDomain:
    """Tests for URL-to-domain extraction."""

    def test_https_url(self):
        assert _extract_domain("https://twitter.com/home") == "twitter.com"

    def test_http_url(self):
        assert _extract_domain("http://example.com/page") == "example.com"

    def test_strips_www(self):
        assert _extract_domain("https://www.google.com/search?q=test") == "google.com"

    def test_subdomain_preserved(self):
        assert _extract_domain("https://docs.google.com/doc/123") == "docs.google.com"

    def test_port_included(self):
        result = _extract_domain("http://localhost:3000/app")
        assert "localhost" in result

    def test_empty_string(self):
        assert _extract_domain("") == ""

    def test_none_returns_empty(self):
        """None URL should not crash."""
        # The code checks `if not url`, so None is handled
        assert _extract_domain(None) == ""

    def test_bare_domain(self):
        result = _extract_domain("example.com")
        assert result == "example.com"

    def test_path_stripped(self):
        result = _extract_domain("https://github.com/user/repo/pulls")
        assert result == "github.com"

    def test_query_params_stripped(self):
        result = _extract_domain("https://google.com?q=test&lang=en")
        assert result == "google.com"

    def test_fragment_stripped(self):
        result = _extract_domain("https://docs.python.org/3/library#section")
        assert result == "docs.python.org"

    def test_lowercase(self):
        result = _extract_domain("https://TWITTER.COM/home")
        assert result == "twitter.com"

    def test_complex_subdomain(self):
        result = _extract_domain("https://sub.domain.example.com/path")
        assert result == "sub.domain.example.com"


# ---------------------------------------------------------------------------
# get_current
# ---------------------------------------------------------------------------


class TestGetCurrent:
    """Tests for getting the current foreground activity."""

    def test_get_current_returns_dict(self):
        result = monitor.get_current()
        assert isinstance(result, dict)

    def test_get_current_has_expected_keys(self):
        result = monitor.get_current()
        assert "app" in result
        assert "title" in result
        assert "url" in result
        assert "domain" in result
        assert "bundle_id" in result

    def test_get_current_returns_copy(self):
        """Modifying the returned dict should not affect internal state."""
        result = monitor.get_current()
        result["app"] = "modified"
        assert monitor.get_current()["app"] != "modified"

    def test_get_current_default_values(self):
        result = monitor.get_current()
        assert result["app"] == ""
        assert result["title"] == ""
        assert result["url"] == ""
        assert result["domain"] == ""
        assert result["bundle_id"] == ""


# ---------------------------------------------------------------------------
# set_browser_url
# ---------------------------------------------------------------------------


class TestSetBrowserUrl:
    """Tests for setting the browser URL externally."""

    def test_set_browser_url(self):
        monitor.set_browser_url("https://twitter.com")
        assert monitor._browser_url == "https://twitter.com"

    def test_set_browser_url_empty(self):
        monitor.set_browser_url("https://test.com")
        monitor.set_browser_url("")
        assert monitor._browser_url == ""

    def test_set_browser_url_overwrites(self):
        monitor.set_browser_url("https://first.com")
        monitor.set_browser_url("https://second.com")
        assert monitor._browser_url == "https://second.com"


# ---------------------------------------------------------------------------
# start / stop
# ---------------------------------------------------------------------------


class TestStartStop:
    """Tests for the polling lifecycle."""

    def test_start_sets_running(self):
        monitor.start()
        assert monitor._running is True
        monitor.stop()

    def test_stop_clears_running(self):
        monitor.start()
        monitor.stop()
        assert monitor._running is False

    def test_stop_without_start_no_crash(self):
        monitor.stop()
        assert monitor._running is False

    def test_double_start_no_duplicate_threads(self):
        """Starting an already running monitor should be a no-op."""
        monitor.start()
        thread1 = monitor._thread
        monitor.start()
        thread2 = monitor._thread
        assert thread1 is thread2
        monitor.stop()
