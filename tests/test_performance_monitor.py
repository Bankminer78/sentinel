"""Tests for sentinel.performance_monitor."""
import pytest
import time
from sentinel import performance_monitor as pm


@pytest.fixture(autouse=True)
def reset():
    pm.reset()
    yield
    pm.reset()


def test_record_operation():
    pm.record_operation("test_op", 50)
    stats = pm.get_operation_stats()
    assert "test_op" in stats
    assert stats["test_op"]["count"] == 1


def test_slow_operations():
    pm.record_operation("slow", 500)
    pm.record_operation("fast", 10)
    slow = pm.get_slow_operations()
    assert any(op["name"] == "slow" for op in slow)


def test_operation_stats():
    pm.record_operation("op1", 100)
    pm.record_operation("op1", 200)
    stats = pm.get_operation_stats()
    assert stats["op1"]["count"] == 2
    assert stats["op1"]["avg_ms"] == 150


def test_slowest_operations():
    pm.record_operation("fast", 10)
    pm.record_operation("slow", 1000)
    slowest = pm.slowest_operations()
    assert slowest[0]["name"] == "slow"


def test_reset():
    pm.record_operation("op", 100)
    pm.reset()
    assert pm.operation_count() == 0


def test_timing_decorator():
    @pm.timing("decorated")
    def my_func():
        return 42

    result = my_func()
    assert result == 42
    stats = pm.get_operation_stats()
    assert "decorated" in stats


def test_timer_context():
    with pm.Timer("block_op"):
        time.sleep(0.01)
    stats = pm.get_operation_stats()
    assert "block_op" in stats


def test_operation_count():
    pm.record_operation("a", 10)
    pm.record_operation("a", 20)
    pm.record_operation("b", 30)
    assert pm.operation_count() == 3
    assert pm.operation_count("a") == 2


def test_total_time():
    pm.record_operation("op", 100)
    pm.record_operation("op", 200)
    assert pm.total_time_ms("op") == 300


def test_summary():
    pm.record_operation("op", 50)
    pm.record_operation("slow", 500)
    summary = pm.summary()
    assert summary["total_operations"] == 2
    assert summary["slow_operations_count"] >= 1
