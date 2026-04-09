"""Tests for sentinel.cron."""
import pytest
import time
from sentinel import cron, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_task(conn):
    tid = cron.add_task(conn, "daily_report", "@daily", "report")
    assert tid > 0


def test_list_tasks_empty(conn):
    assert cron.list_tasks(conn) == []


def test_list_tasks(conn):
    cron.add_task(conn, "t1", "@hourly", "action1")
    cron.add_task(conn, "t2", "@daily", "action2")
    assert len(cron.list_tasks(conn)) == 2


def test_delete_task(conn):
    tid = cron.add_task(conn, "t", "@daily", "a")
    cron.delete_task(conn, tid)
    assert cron.list_tasks(conn) == []


def test_enable_disable(conn):
    tid = cron.add_task(conn, "t", "@daily", "a")
    cron.disable_task(conn, tid)
    tasks = cron.list_tasks(conn)
    assert tasks[0]["enabled"] == 0
    cron.enable_task(conn, tid)
    tasks = cron.list_tasks(conn)
    assert tasks[0]["enabled"] == 1


def test_expression_interval():
    assert cron._expression_interval_seconds("@hourly") == 3600
    assert cron._expression_interval_seconds("@daily") == 86400
    assert cron._expression_interval_seconds("@weekly") == 604800


def test_expression_minutes():
    assert cron._expression_interval_seconds("every 15 minutes") == 900


def test_expression_hours():
    assert cron._expression_interval_seconds("every 3 hours") == 10800


def test_due_tasks(conn):
    cron.add_task(conn, "t", "@hourly", "a")
    due = cron.due_tasks(conn)
    assert len(due) == 1  # Never run, so it's due


def test_due_tasks_disabled(conn):
    tid = cron.add_task(conn, "t", "@hourly", "a")
    cron.disable_task(conn, tid)
    due = cron.due_tasks(conn)
    assert due == []


def test_mark_task_run(conn):
    tid = cron.add_task(conn, "t", "@hourly", "a")
    cron.mark_task_run(conn, tid)
    # Should no longer be due
    due = cron.due_tasks(conn)
    assert not any(d["id"] == tid for d in due)


def test_task_next_run(conn):
    tid = cron.add_task(conn, "t", "@hourly", "a")
    cron.mark_task_run(conn, tid)
    next_run = cron.task_next_run(conn, tid)
    assert next_run > time.time()
