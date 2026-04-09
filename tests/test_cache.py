"""Tests for sentinel.cache."""
import pytest
import time
from sentinel import cache


@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()
    yield
    cache.clear()


def test_set_get():
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"


def test_get_missing():
    assert cache.get("missing") is None


def test_get_with_default():
    assert cache.get("missing", default="default") == "default"


def test_has():
    cache.set("key", "value")
    assert cache.has("key") is True
    assert cache.has("missing") is False


def test_delete():
    cache.set("key", "value")
    cache.delete("key")
    assert cache.has("key") is False


def test_clear():
    cache.set("k1", "v1")
    cache.set("k2", "v2")
    cache.clear()
    assert cache.size() == 0


def test_keys():
    cache.set("k1", "v1")
    cache.set("k2", "v2")
    keys = cache.keys()
    assert "k1" in keys
    assert "k2" in keys


def test_size():
    cache.set("k1", "v1")
    cache.set("k2", "v2")
    assert cache.size() == 2


def test_ttl_expiration():
    cache.set("expire", "value", ttl_seconds=0)
    time.sleep(0.01)
    assert cache.get("expire") is None


def test_purge_expired():
    cache.set("keep", "value", ttl_seconds=300)
    cache.set("expire", "value", ttl_seconds=0)
    time.sleep(0.01)
    purged = cache.purge_expired()
    assert purged >= 1


def test_stats():
    cache.set("k1", "v1")
    stats = cache.stats()
    assert stats["size"] == 1


def test_cached_decorator():
    call_count = [0]

    @cache.cached(ttl_seconds=300)
    def expensive(x):
        call_count[0] += 1
        return x * 2

    assert expensive(5) == 10
    assert expensive(5) == 10
    assert call_count[0] == 1  # Cached


def test_store_complex_value():
    cache.set("list", [1, 2, 3])
    assert cache.get("list") == [1, 2, 3]


def test_store_dict():
    cache.set("dict", {"a": 1})
    assert cache.get("dict") == {"a": 1}
