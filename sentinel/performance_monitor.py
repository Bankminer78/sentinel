"""Performance monitor — track slow operations and query times."""
import time
from collections import deque


_slow_operations = deque(maxlen=100)
_op_counts = {}
_op_total_time = {}


def record_operation(name: str, duration_ms: float, details: dict = None):
    """Record an operation's duration."""
    if name not in _op_counts:
        _op_counts[name] = 0
        _op_total_time[name] = 0
    _op_counts[name] += 1
    _op_total_time[name] += duration_ms
    if duration_ms > 100:
        _slow_operations.append({
            "name": name,
            "duration_ms": duration_ms,
            "details": details or {},
            "ts": time.time(),
        })


def get_slow_operations(limit: int = 20) -> list:
    return list(_slow_operations)[-limit:][::-1]


def get_operation_stats() -> dict:
    stats = {}
    for op in _op_counts:
        count = _op_counts[op]
        total = _op_total_time[op]
        stats[op] = {
            "count": count,
            "total_ms": round(total, 2),
            "avg_ms": round(total / count, 2) if count > 0 else 0,
        }
    return stats


def slowest_operations(limit: int = 10) -> list:
    stats = get_operation_stats()
    sorted_ops = sorted(
        stats.items(), key=lambda x: x[1]["avg_ms"], reverse=True)
    return [{"name": name, **data} for name, data in sorted_ops[:limit]]


def reset():
    global _op_counts, _op_total_time
    _slow_operations.clear()
    _op_counts = {}
    _op_total_time = {}


def timing(name: str):
    """Decorator to time a function."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            duration = (time.time() - start) * 1000
            record_operation(name, duration)
            return result
        return wrapper
    return decorator


class Timer:
    """Context manager for timing blocks."""
    def __init__(self, name: str):
        self.name = name
        self.start = None

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        duration = (time.time() - self.start) * 1000
        record_operation(self.name, duration)


def operation_count(name: str = None) -> int:
    if name:
        return _op_counts.get(name, 0)
    return sum(_op_counts.values())


def total_time_ms(name: str = None) -> float:
    if name:
        return _op_total_time.get(name, 0)
    return sum(_op_total_time.values())


def summary() -> dict:
    return {
        "total_operations": operation_count(),
        "slow_operations_count": len(_slow_operations),
        "tracked_types": len(_op_counts),
        "total_time_ms": round(total_time_ms(), 2),
    }
