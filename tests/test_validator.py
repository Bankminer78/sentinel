"""Tests for sentinel.validator."""
import pytest
from sentinel import validator as v


class TestDomain:
    def test_valid_domain(self):
        assert v.is_valid_domain("example.com") is True

    def test_valid_subdomain(self):
        assert v.is_valid_domain("sub.example.com") is True

    def test_invalid_no_tld(self):
        assert v.is_valid_domain("example") is False

    def test_invalid_empty(self):
        assert v.is_valid_domain("") is False

    def test_invalid_none(self):
        assert v.is_valid_domain(None) is False

    def test_invalid_scheme(self):
        assert v.is_valid_domain("http://example.com") is False


class TestUrl:
    def test_valid_http(self):
        assert v.is_valid_url("http://example.com") is True

    def test_valid_https(self):
        assert v.is_valid_url("https://example.com/path") is True

    def test_invalid_no_scheme(self):
        assert v.is_valid_url("example.com") is False

    def test_invalid_empty(self):
        assert v.is_valid_url("") is False


class TestTime:
    def test_valid_midnight(self):
        assert v.is_valid_time("00:00") is True

    def test_valid_end(self):
        assert v.is_valid_time("23:59") is True

    def test_invalid_hour(self):
        assert v.is_valid_time("24:00") is False

    def test_invalid_minute(self):
        assert v.is_valid_time("12:60") is False

    def test_invalid_format(self):
        assert v.is_valid_time("9:00") is False

    def test_invalid_non_string(self):
        assert v.is_valid_time(None) is False


class TestDay:
    def test_valid_short(self):
        assert v.is_valid_day("mon") is True

    def test_valid_long(self):
        assert v.is_valid_day("Monday") is True

    def test_valid_all(self):
        assert v.is_valid_day("all") is True

    def test_invalid(self):
        assert v.is_valid_day("funday") is False


class TestBundleId:
    def test_valid(self):
        assert v.is_valid_bundle_id("com.apple.Safari") is True

    def test_invalid_no_dot(self):
        assert v.is_valid_bundle_id("Safari") is False

    def test_invalid_empty(self):
        assert v.is_valid_bundle_id("") is False


class TestSanitizeRuleText:
    def test_removes_control_chars(self):
        assert v.sanitize_rule_text("hello\x00world") == "helloworld"

    def test_collapses_whitespace(self):
        assert v.sanitize_rule_text("a   b\n\tc") == "a b c"

    def test_truncates_long(self):
        assert len(v.sanitize_rule_text("x" * 1000)) == 500

    def test_none_returns_empty(self):
        assert v.sanitize_rule_text(None) == ""


class TestSanitizeFilename:
    def test_replaces_bad_chars(self):
        assert v.sanitize_filename("a/b:c*d") == "a_b_c_d"

    def test_empty_becomes_unnamed(self):
        assert v.sanitize_filename("///") == "unnamed"

    def test_keeps_dots_and_hyphens(self):
        assert v.sanitize_filename("my-file.txt") == "my-file.txt"


class TestNormalizeDomain:
    def test_strips_scheme(self):
        assert v.normalize_domain("https://example.com") == "example.com"

    def test_strips_www(self):
        assert v.normalize_domain("www.example.com") == "example.com"

    def test_strips_path(self):
        assert v.normalize_domain("example.com/foo") == "example.com"

    def test_strips_port(self):
        assert v.normalize_domain("example.com:8080") == "example.com"

    def test_lowercases(self):
        assert v.normalize_domain("EXAMPLE.com") == "example.com"


class TestValidateRuleDict:
    def test_valid_empty(self):
        ok, _ = v.validate_rule_dict({})
        assert ok is True

    def test_invalid_not_dict(self):
        ok, msg = v.validate_rule_dict("not a dict")
        assert ok is False

    def test_valid_action(self):
        ok, _ = v.validate_rule_dict({"action": "block"})
        assert ok is True

    def test_invalid_action(self):
        ok, _ = v.validate_rule_dict({"action": "explode"})
        assert ok is False

    def test_invalid_domains_type(self):
        ok, _ = v.validate_rule_dict({"domains": "not a list"})
        assert ok is False

    def test_valid_domain_wildcard(self):
        ok, _ = v.validate_rule_dict({"domains": ["*.youtube.com"]})
        assert ok is True

    def test_invalid_schedule_time(self):
        ok, _ = v.validate_rule_dict({"schedule": {"start": "25:00", "end": "12:00"}})
        assert ok is False

    def test_valid_schedule(self):
        ok, _ = v.validate_rule_dict({"schedule": {"start": "09:00", "end": "17:00"}})
        assert ok is True

    def test_invalid_allowed_minutes_negative(self):
        ok, _ = v.validate_rule_dict({"allowed_minutes": -1})
        assert ok is False
