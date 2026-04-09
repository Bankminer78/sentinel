"""Tests for sentinel.skiplist — Domain skiplist (module-level functions)."""

import pytest

from sentinel.skiplist import should_skip, SKIP_DOMAINS, SKIP_PATTERNS, SKIP_SUFFIXES


# ---------------------------------------------------------------------------
# should_skip — exact domain matching
# ---------------------------------------------------------------------------


class TestSkiplistExactMatch:
    """Tests for exact domain matching."""

    def test_skip_google(self):
        assert should_skip("google.com") is True

    def test_skip_github(self):
        assert should_skip("github.com") is True

    def test_skip_stackoverflow(self):
        assert should_skip("stackoverflow.com") is True

    def test_skip_apple(self):
        assert should_skip("apple.com") is True

    def test_skip_claude_ai(self):
        assert should_skip("claude.ai") is True

    def test_do_not_skip_twitter(self):
        assert should_skip("twitter.com") is False

    def test_do_not_skip_youtube(self):
        assert should_skip("youtube.com") is False

    def test_do_not_skip_reddit(self):
        assert should_skip("reddit.com") is False

    def test_do_not_skip_facebook(self):
        assert should_skip("facebook.com") is False

    def test_do_not_skip_instagram(self):
        assert should_skip("instagram.com") is False

    def test_do_not_skip_tiktok(self):
        assert should_skip("tiktok.com") is False

    def test_do_not_skip_unknown(self):
        assert should_skip("random-unknown-site.example.com") is False

    def test_empty_domain_should_skip(self):
        assert should_skip("") is True


# ---------------------------------------------------------------------------
# should_skip — parent domain matching
# ---------------------------------------------------------------------------


class TestSkiplistParentDomain:
    """Tests for parent domain matching (subdomain -> parent -> skip)."""

    def test_calendar_google_inherits(self):
        assert should_skip("calendar.google.com") is True

    def test_mail_google_inherits(self):
        assert should_skip("mail.google.com") is True

    def test_drive_google_inherits(self):
        assert should_skip("drive.google.com") is True

    def test_docs_google_inherits(self):
        assert should_skip("docs.google.com") is True

    def test_deep_subdomain_google(self):
        assert should_skip("foo.bar.google.com") is True

    def test_subdomain_of_non_skiplist_not_skipped(self):
        assert should_skip("api.twitter.com") is False

    def test_www_apple(self):
        assert should_skip("www.apple.com") is True

    def test_subdomain_of_reddit_not_skipped(self):
        assert should_skip("old.reddit.com") is False

    def test_gist_github(self):
        assert should_skip("gist.github.com") is True

    def test_deep_subdomain_apple(self):
        assert should_skip("foo.bar.apple.com") is True


# ---------------------------------------------------------------------------
# should_skip — pattern matching (startswith / endswith)
# ---------------------------------------------------------------------------


class TestSkiplistPatterns:
    """Tests for prefix and suffix matching."""

    def test_localhost(self):
        assert should_skip("localhost") is True

    def test_localhost_with_port(self):
        assert should_skip("localhost:3000") is True

    def test_localhost_8080(self):
        assert should_skip("localhost:8080") is True

    def test_127_0_0_1(self):
        assert should_skip("127.0.0.1") is True

    def test_127_0_0_1_with_port(self):
        assert should_skip("127.0.0.1:8000") is True

    def test_private_ip_192(self):
        assert should_skip("192.168.1.1") is True

    def test_private_ip_10(self):
        assert should_skip("10.0.0.1") is True

    def test_0_0_0_0(self):
        assert should_skip("0.0.0.0") is True

    def test_internal_suffix(self):
        assert should_skip("my-app.internal") is True

    def test_local_suffix(self):
        assert should_skip("my-machine.local") is True

    def test_fly_dev_suffix(self):
        assert should_skip("myapp.fly.dev") is True

    def test_vercel_app_suffix(self):
        assert should_skip("myapp.vercel.app") is True

    def test_public_ip_not_skipped(self):
        assert should_skip("8.8.8.8") is False


# ---------------------------------------------------------------------------
# should_skip — edge cases
# ---------------------------------------------------------------------------


class TestSkiplistEdgeCases:
    """Edge cases and boundary conditions."""

    def test_case_insensitive(self):
        assert should_skip("Google.Com") is True
        assert should_skip("APPLE.COM") is True

    def test_single_label_localhost(self):
        assert should_skip("localhost") is True

    def test_very_long_domain(self):
        long_domain = "a" * 200 + ".example.com"
        result = should_skip(long_domain)
        assert isinstance(result, bool)

    def test_numeric_private_ip(self):
        assert should_skip("192.168.1.1") is True

    def test_cdn_domains_are_bool(self):
        """CDN domains should return a bool (may or may not be in skiplist)."""
        for domain in ["cdn.jsdelivr.net", "fonts.googleapis.com"]:
            result = should_skip(domain)
            assert isinstance(result, bool)

    def test_skip_domains_is_set(self):
        assert isinstance(SKIP_DOMAINS, set)

    def test_skip_patterns_is_tuple(self):
        assert isinstance(SKIP_PATTERNS, tuple)

    def test_skip_suffixes_is_tuple(self):
        assert isinstance(SKIP_SUFFIXES, tuple)
