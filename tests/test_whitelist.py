"""Tests for sentinel.whitelist."""
import pytest
from sentinel import whitelist, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_enable_mode(conn):
    whitelist.enable_whitelist_mode(conn)
    assert whitelist.is_whitelist_mode(conn) is True


def test_disable_mode(conn):
    whitelist.enable_whitelist_mode(conn)
    whitelist.disable_whitelist_mode(conn)
    assert whitelist.is_whitelist_mode(conn) is False


def test_mode_default_off(conn):
    assert whitelist.is_whitelist_mode(conn) is False


def test_add_domain(conn):
    whitelist.add_to_whitelist(conn, "github.com")
    assert "github.com" in whitelist.get_whitelist(conn)


def test_add_lowercase(conn):
    whitelist.add_to_whitelist(conn, "GITHUB.COM")
    assert "github.com" in whitelist.get_whitelist(conn)


def test_add_duplicate(conn):
    whitelist.add_to_whitelist(conn, "github.com")
    whitelist.add_to_whitelist(conn, "github.com")
    assert len(whitelist.get_whitelist(conn)) == 1


def test_remove_domain(conn):
    whitelist.add_to_whitelist(conn, "github.com")
    whitelist.remove_from_whitelist(conn, "github.com")
    assert "github.com" not in whitelist.get_whitelist(conn)


def test_remove_nonexistent(conn):
    whitelist.remove_from_whitelist(conn, "ghost.com")  # Should not raise


def test_is_whitelisted_exact(conn):
    whitelist.add_to_whitelist(conn, "github.com")
    assert whitelist.is_whitelisted(conn, "github.com") is True


def test_is_whitelisted_subdomain(conn):
    whitelist.add_to_whitelist(conn, "github.com")
    assert whitelist.is_whitelisted(conn, "gist.github.com") is True


def test_is_whitelisted_deep_subdomain(conn):
    whitelist.add_to_whitelist(conn, "google.com")
    assert whitelist.is_whitelisted(conn, "deep.nested.google.com") is True


def test_is_not_whitelisted(conn):
    whitelist.add_to_whitelist(conn, "github.com")
    assert whitelist.is_whitelisted(conn, "facebook.com") is False


def test_empty_whitelist(conn):
    assert whitelist.get_whitelist(conn) == []


def test_multiple_domains(conn):
    for d in ["github.com", "google.com", "claude.ai"]:
        whitelist.add_to_whitelist(conn, d)
    result = whitelist.get_whitelist(conn)
    assert len(result) == 3
    assert "github.com" in result
    assert "google.com" in result
