"""Tests for sentinel.url_shortener."""
import pytest
from sentinel import url_shortener as us, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_shorten(conn):
    code = us.shorten(conn, "https://example.com")
    assert code
    assert len(code) >= 4


def test_expand(conn):
    code = us.shorten(conn, "https://example.com")
    long_url = us.expand(conn, code)
    assert long_url == "https://example.com"


def test_expand_nonexistent(conn):
    assert us.expand(conn, "nonexistent") is None


def test_get_stats(conn):
    code = us.shorten(conn, "https://example.com")
    us.expand(conn, code)
    stats = us.get_stats(conn, code)
    assert stats["click_count"] == 1


def test_list_all(conn):
    us.shorten(conn, "https://a.com")
    us.shorten(conn, "https://b.com")
    assert len(us.list_all(conn)) == 2


def test_delete(conn):
    code = us.shorten(conn, "https://test.com")
    us.delete(conn, code)
    assert us.expand(conn, code) is None


def test_most_clicked(conn):
    code1 = us.shorten(conn, "https://a.com")
    code2 = us.shorten(conn, "https://b.com")
    us.expand(conn, code1)
    us.expand(conn, code1)
    us.expand(conn, code2)
    top = us.most_clicked(conn)
    assert top[0]["code"] == code1


def test_total_count(conn):
    us.shorten(conn, "https://a.com")
    us.shorten(conn, "https://b.com")
    assert us.total_count(conn) == 2


def test_total_clicks(conn):
    code = us.shorten(conn, "https://a.com")
    us.expand(conn, code)
    us.expand(conn, code)
    assert us.total_clicks(conn) == 2


def test_generate_code_unique():
    import time
    c1 = us._generate_code("https://test.com")
    time.sleep(0.001)
    c2 = us._generate_code("https://test.com")
    assert c1 != c2
