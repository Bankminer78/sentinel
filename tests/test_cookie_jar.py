"""Tests for sentinel.cookie_jar."""
import pytest
from sentinel import cookie_jar as cj, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_cookie(conn):
    cid = cj.add_cookie(conn, "Launched the feature", "win")
    assert cid > 0


def test_get_cookies(conn):
    cj.add_cookie(conn, "Win 1")
    cj.add_cookie(conn, "Win 2")
    assert len(cj.get_cookies(conn)) == 2


def test_random_cookie_empty(conn):
    assert cj.random_cookie(conn) is None


def test_random_cookie(conn):
    cj.add_cookie(conn, "Test win")
    r = cj.random_cookie(conn)
    assert r["content"] == "Test win"


def test_delete_cookie(conn):
    cid = cj.add_cookie(conn, "Delete me")
    cj.delete_cookie(conn, cid)
    assert cj.count_cookies(conn) == 0


def test_count_cookies(conn):
    cj.add_cookie(conn, "W1", "win")
    cj.add_cookie(conn, "G1", "gratitude")
    assert cj.count_cookies(conn) == 2
    assert cj.count_cookies(conn, "win") == 1


def test_categories(conn):
    cj.add_cookie(conn, "c1", "win")
    cj.add_cookie(conn, "c2", "gratitude")
    cats = cj.categories(conn)
    assert len(cats) == 2


def test_search_cookies(conn):
    cj.add_cookie(conn, "Launched feature X")
    results = cj.search_cookies(conn, "Launched")
    assert len(results) == 1


def test_cookies_this_month(conn):
    cj.add_cookie(conn, "This month")
    assert cj.cookies_this_month(conn) >= 1


def test_oldest_cookie(conn):
    cj.add_cookie(conn, "First")
    import time
    time.sleep(0.01)
    cj.add_cookie(conn, "Second")
    oldest = cj.oldest_cookie(conn)
    assert oldest["content"] == "First"


def test_jar_summary(conn):
    cj.add_cookie(conn, "W", "win")
    cj.add_cookie(conn, "G", "gratitude")
    summary = cj.jar_summary(conn)
    assert summary["total"] == 2
    assert summary["wins"] == 1
