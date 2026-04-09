"""API rate limiting — prevent abuse of LLM endpoints."""
import time
from collections import defaultdict


_buckets = defaultdict(list)  # key -> list of timestamps


def check_rate_limit(key: str, max_calls: int = 60, window_seconds: int = 60) -> bool:
    """Check if a caller is within rate limit. Returns True if allowed."""
    now = time.time()
    cutoff = now - window_seconds
    _buckets[key] = [t for t in _buckets[key] if t > cutoff]
    if len(_buckets[key]) >= max_calls:
        return False
    _buckets[key].append(now)
    return True


def get_usage(key: str, window_seconds: int = 60) -> int:
    """Get current usage count in window."""
    now = time.time()
    cutoff = now - window_seconds
    _buckets[key] = [t for t in _buckets[key] if t > cutoff]
    return len(_buckets[key])


def reset_key(key: str):
    if key in _buckets:
        del _buckets[key]


def reset_all():
    _buckets.clear()


def get_time_until_reset(key: str, max_calls: int = 60, window_seconds: int = 60) -> float:
    """Seconds until the oldest call expires and a slot frees up."""
    if not _buckets.get(key) or len(_buckets[key]) < max_calls:
        return 0
    oldest = min(_buckets[key])
    return max(0, (oldest + window_seconds) - time.time())


def all_buckets() -> dict:
    """Return all bucket usage counts."""
    return {k: len(v) for k, v in _buckets.items()}


class RateLimiter:
    """Class-based rate limiter for specific endpoints."""
    def __init__(self, max_calls: int = 60, window_seconds: int = 60):
        self.max_calls = max_calls
        self.window_seconds = window_seconds

    def allow(self, key: str) -> bool:
        return check_rate_limit(key, self.max_calls, self.window_seconds)

    def usage(self, key: str) -> int:
        return get_usage(key, self.window_seconds)
