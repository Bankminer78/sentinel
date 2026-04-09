"""Tests for sentinel.rate_limit."""
import pytest
from sentinel import rate_limit


@pytest.fixture(autouse=True)
def reset_buckets():
    rate_limit.reset_all()
    yield
    rate_limit.reset_all()


def test_allow_under_limit():
    assert rate_limit.check_rate_limit("user1", max_calls=5) is True


def test_deny_over_limit():
    for _ in range(5):
        rate_limit.check_rate_limit("user2", max_calls=5)
    assert rate_limit.check_rate_limit("user2", max_calls=5) is False


def test_get_usage():
    rate_limit.check_rate_limit("user3")
    rate_limit.check_rate_limit("user3")
    assert rate_limit.get_usage("user3") == 2


def test_reset_key():
    rate_limit.check_rate_limit("user4")
    rate_limit.reset_key("user4")
    assert rate_limit.get_usage("user4") == 0


def test_reset_all():
    rate_limit.check_rate_limit("a")
    rate_limit.check_rate_limit("b")
    rate_limit.reset_all()
    assert rate_limit.all_buckets() == {}


def test_independent_keys():
    rate_limit.check_rate_limit("alice", max_calls=2)
    rate_limit.check_rate_limit("alice", max_calls=2)
    rate_limit.check_rate_limit("bob", max_calls=2)
    assert rate_limit.get_usage("alice") == 2
    assert rate_limit.get_usage("bob") == 1


def test_rate_limiter_class():
    limiter = rate_limit.RateLimiter(max_calls=3, window_seconds=60)
    assert limiter.allow("test") is True
    assert limiter.allow("test") is True
    assert limiter.allow("test") is True
    assert limiter.allow("test") is False


def test_get_time_until_reset():
    rate_limit.reset_all()
    # Not at limit yet
    rate_limit.check_rate_limit("x", max_calls=5)
    assert rate_limit.get_time_until_reset("x", max_calls=5) == 0


def test_rate_limiter_usage():
    limiter = rate_limit.RateLimiter(max_calls=10, window_seconds=60)
    limiter.allow("user")
    limiter.allow("user")
    assert limiter.usage("user") == 2


def test_all_buckets():
    rate_limit.check_rate_limit("x")
    rate_limit.check_rate_limit("y")
    buckets = rate_limit.all_buckets()
    assert "x" in buckets
    assert "y" in buckets
