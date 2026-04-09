"""Tests for sentinel.todo."""
import pytest
from datetime import datetime, timedelta
from sentinel import todo, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_todo(conn):
    tid = todo.add_todo(conn, "Write report", priority=3)
    assert tid > 0


def test_get_todos(conn):
    todo.add_todo(conn, "T1")
    todo.add_todo(conn, "T2")
    assert len(todo.get_todos(conn)) == 2


def test_complete_todo(conn):
    tid = todo.add_todo(conn, "Test")
    todo.complete_todo(conn, tid)
    assert len(todo.get_todos(conn, completed=True)) == 1
    assert len(todo.get_todos(conn, completed=False)) == 0


def test_uncomplete_todo(conn):
    tid = todo.add_todo(conn, "Test")
    todo.complete_todo(conn, tid)
    todo.uncomplete_todo(conn, tid)
    assert len(todo.get_todos(conn, completed=False)) == 1


def test_delete_todo(conn):
    tid = todo.add_todo(conn, "Delete")
    todo.delete_todo(conn, tid)
    assert todo.get_todo(conn, tid) is None


def test_get_todo(conn):
    tid = todo.add_todo(conn, "Test", priority=5)
    t = todo.get_todo(conn, tid)
    assert t["priority"] == 5


def test_overdue_todos(conn):
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    todo.add_todo(conn, "Overdue", due_date=yesterday)
    assert len(todo.overdue_todos(conn)) == 1


def test_due_today(conn):
    today = datetime.now().strftime("%Y-%m-%d")
    todo.add_todo(conn, "Today", due_date=today)
    assert len(todo.due_today(conn)) == 1


def test_high_priority(conn):
    todo.add_todo(conn, "Low", priority=0)
    todo.add_todo(conn, "High", priority=5)
    high = todo.high_priority(conn)
    assert len(high) == 1


def test_todos_by_tag(conn):
    todo.add_todo(conn, "Work task", tags="work")
    todo.add_todo(conn, "Home task", tags="home")
    work = todo.todos_by_tag(conn, "work")
    assert len(work) == 1


def test_todo_count(conn):
    todo.add_todo(conn, "T1")
    tid = todo.add_todo(conn, "T2")
    todo.complete_todo(conn, tid)
    count = todo.todo_count(conn)
    assert count["total"] == 2
    assert count["done"] == 1
    assert count["remaining"] == 1


def test_priority_sorting(conn):
    todo.add_todo(conn, "Low", priority=0)
    todo.add_todo(conn, "High", priority=5)
    todo.add_todo(conn, "Medium", priority=2)
    todos = todo.get_todos(conn)
    # Should be sorted by priority descending
    assert todos[0]["text"] == "High"
