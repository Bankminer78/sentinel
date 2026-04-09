"""Tests for sentinel.habits."""
import datetime as _dt
from sentinel import habits


def test_add_habit(conn):
    hid = habits.add_habit(conn, "meditate")
    assert hid > 0


def test_add_habit_with_target(conn):
    hid = habits.add_habit(conn, "water", "daily", target=8)
    hs = habits.get_habits(conn)
    assert hs[0]["target"] == 8


def test_get_habits_empty(conn):
    assert habits.get_habits(conn) == []


def test_get_habits(conn):
    habits.add_habit(conn, "read")
    habits.add_habit(conn, "exercise")
    assert len(habits.get_habits(conn)) == 2


def test_log_habit(conn):
    hid = habits.add_habit(conn, "meditate")
    entry = habits.log_habit(conn, hid)
    assert entry["count"] == 1


def test_log_habit_increments(conn):
    hid = habits.add_habit(conn, "water", target=3)
    habits.log_habit(conn, hid)
    entry = habits.log_habit(conn, hid)
    assert entry["count"] == 2


def test_log_habit_specific_date(conn):
    hid = habits.add_habit(conn, "run")
    entry = habits.log_habit(conn, hid, "2025-01-01")
    assert entry["date"] == "2025-01-01"


def test_delete_habit(conn):
    hid = habits.add_habit(conn, "temp")
    habits.log_habit(conn, hid)
    habits.delete_habit(conn, hid)
    assert habits.get_habits(conn) == []


def test_stats_empty(conn):
    hid = habits.add_habit(conn, "new")
    s = habits.get_habit_stats(conn, hid)
    assert s["total_days"] == 0
    assert s["current_streak"] == 0


def test_stats_single_day(conn):
    hid = habits.add_habit(conn, "read")
    habits.log_habit(conn, hid)
    s = habits.get_habit_stats(conn, hid)
    assert s["total_days"] == 1
    assert s["current_streak"] == 1


def test_stats_streak(conn):
    hid = habits.add_habit(conn, "read")
    today = _dt.date.today()
    for i in range(3):
        habits.log_habit(conn, hid, (today - _dt.timedelta(days=i)).isoformat())
    s = habits.get_habit_stats(conn, hid)
    assert s["current_streak"] == 3
    assert s["longest_streak"] == 3


def test_stats_broken_streak(conn):
    hid = habits.add_habit(conn, "read")
    today = _dt.date.today()
    for d in [today, today - _dt.timedelta(days=1), today - _dt.timedelta(days=5)]:
        habits.log_habit(conn, hid, d.isoformat())
    s = habits.get_habit_stats(conn, hid)
    assert s["current_streak"] == 2
    assert s["total_days"] == 3


def test_stats_no_current_streak(conn):
    hid = habits.add_habit(conn, "read")
    old = _dt.date.today() - _dt.timedelta(days=10)
    habits.log_habit(conn, hid, old.isoformat())
    s = habits.get_habit_stats(conn, hid)
    assert s["current_streak"] == 0


def test_todays_habits(conn):
    hid1 = habits.add_habit(conn, "a")
    hid2 = habits.add_habit(conn, "b", target=2)
    habits.log_habit(conn, hid1)
    today = habits.get_todays_habits(conn)
    by_id = {h["id"]: h for h in today}
    assert by_id[hid1]["done"] is True
    assert by_id[hid2]["done"] is False


def test_todays_habits_empty(conn):
    assert habits.get_todays_habits(conn) == []


def test_log_habit_multiple_habits(conn):
    hid1 = habits.add_habit(conn, "a")
    hid2 = habits.add_habit(conn, "b")
    habits.log_habit(conn, hid1)
    habits.log_habit(conn, hid2)
    assert len(habits.get_todays_habits(conn)) == 2


def test_delete_habit_clears_logs(conn):
    hid = habits.add_habit(conn, "temp")
    habits.log_habit(conn, hid)
    habits.delete_habit(conn, hid)
    s = habits.get_habit_stats(conn, hid)
    assert s["total_days"] == 0
