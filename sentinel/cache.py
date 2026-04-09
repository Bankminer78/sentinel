"""Simple in-memory cache with TTL."""
import time


_store = {}


def set(key: str, value, ttl_seconds: int = 300):
    _store[key] = (value, time.time() + ttl_seconds)


def get(key: str, default=None):
    if key not in _store:
        return default
    value, expires = _store[key]
    if time.time() > expires:
        del _store[key]
        return default
    return value


def delete(key: str):
    if key in _store:
        del _store[key]


def clear():
    _store.clear()


def has(key: str) -> bool:
    if key not in _store:
        return False
    _, expires = _store[key]
    if time.time() > expires:
        del _store[key]
        return False
    return True


def keys() -> list:
    """Return all non-expired keys."""
    now = time.time()
    return [k for k, (_, expires) in _store.items() if expires > now]


def size() -> int:
    return len(keys())


def purge_expired() -> int:
    now = time.time()
    expired = [k for k, (_, expires) in _store.items() if expires <= now]
    for k in expired:
        del _store[k]
    return len(expired)


def stats() -> dict:
    return {
        "size": size(),
        "total_entries": len(_store),
    }


def cached(ttl_seconds: int = 300):
    """Decorator to cache function results."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{args}:{kwargs}"
            cached_val = get(key)
            if cached_val is not None:
                return cached_val
            result = func(*args, **kwargs)
            set(key, result, ttl_seconds)
            return result
        return wrapper
    return decorator
