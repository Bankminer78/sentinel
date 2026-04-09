"""Tests for sentinel.content_filter."""
import pytest
from sentinel import content_filter as cf, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_filter(conn):
    fid = cf.add_filter(conn, "nsfw", "block")
    assert fid > 0


def test_get_filters(conn):
    cf.add_filter(conn, "keyword1")
    cf.add_filter(conn, "keyword2")
    assert len(cf.get_filters(conn)) == 2


def test_delete_filter(conn):
    fid = cf.add_filter(conn, "test")
    cf.delete_filter(conn, fid)
    assert cf.count_filters(conn) == 0


def test_matches_contains():
    rule = {"keyword": "test", "match_type": "contains", "case_sensitive": False}
    assert cf.matches_filter("This is a test", rule) is True


def test_matches_case_sensitive():
    rule = {"keyword": "Test", "match_type": "contains", "case_sensitive": True}
    assert cf.matches_filter("this is a test", rule) is False
    assert cf.matches_filter("This is a Test", rule) is True


def test_matches_exact():
    rule = {"keyword": "hello", "match_type": "exact", "case_sensitive": False}
    assert cf.matches_filter("hello", rule) is True
    assert cf.matches_filter("hello world", rule) is False


def test_matches_starts_with():
    rule = {"keyword": "hello", "match_type": "starts_with", "case_sensitive": False}
    assert cf.matches_filter("hello world", rule) is True
    assert cf.matches_filter("world hello", rule) is False


def test_matches_ends_with():
    rule = {"keyword": "world", "match_type": "ends_with", "case_sensitive": False}
    assert cf.matches_filter("hello world", rule) is True


def test_matches_regex():
    rule = {"keyword": r"\d+", "match_type": "regex", "case_sensitive": True}
    assert cf.matches_filter("abc 123 def", rule) is True
    assert cf.matches_filter("abc def", rule) is False


def test_check_content(conn):
    cf.add_filter(conn, "nsfw", action="block")
    result = cf.check_content(conn, "this is nsfw content")
    assert result["should_block"] is True


def test_check_content_no_match(conn):
    cf.add_filter(conn, "nsfw", action="block")
    result = cf.check_content(conn, "clean content")
    assert result["should_block"] is False


def test_filters_by_action(conn):
    cf.add_filter(conn, "a", action="block")
    cf.add_filter(conn, "b", action="warn")
    blocks = cf.filters_by_action(conn, "block")
    assert len(blocks) == 1


def test_test_filter():
    assert cf.test_filter("test", "this is a test") is True
    assert cf.test_filter("test", "clean content") is False
