"""Tests for sentinel.timeline."""
import pytest
import time
import datetime as _dt
from sentinel import timeline, db


def _log(conn, ts, domain="x.com", verdict="allow"):
    conn.execute(
        "INSERT INTO activity_log (ts, app, title, url, domain, verdict) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (ts, "app", "title", f"https://{domain}", domain, verdict))
    conn.commit()


def _today_ts(hour=10, minute=0):
    d = _dt.datetime.combine(_dt.date.today(), _dt.time(hour, minute))
    return d.timestamp()


def test_get_timeline_empty(conn):
    assert timeline.get_timeline(conn) == []


def test_get_timeline_today(conn):
    _log(conn, _today_ts(10))
    _log(conn, _today_ts(11))
    items = timeline.get_timeline(conn)
    assert len(items) == 2
    assert all(it["type"] == "activity" for it in items)


def test_get_timeline_date_filter(conn):
    _log(conn, _today_ts(10))
    yesterday = (_dt.datetime.now() - _dt.timedelta(days=1)).timestamp()
    _log(conn, yesterday)
    items = timeline.get_timeline(conn)
    assert len(items) == 1


def test_get_timeline_specific_date(conn):
    ts = _dt.datetime(2024, 1, 15, 12, 0).timestamp()
    _log(conn, ts)
    items = timeline.get_timeline(conn, "2024-01-15")
    assert len(items) == 1


def test_get_timeline_sorted(conn):
    _log(conn, _today_ts(14), "b.com")
    _log(conn, _today_ts(9), "a.com")
    items = timeline.get_timeline(conn)
    assert items[0]["domain"] == "a.com"
    assert items[1]["domain"] == "b.com"


def test_timeline_with_events_includes_focus(conn):
    db.save_focus_session(conn, _today_ts(10), 25, True)
    _log(conn, _today_ts(11))
    items = timeline.get_timeline_with_events(conn)
    kinds = [it["type"] for it in items]
    assert "focus_session" in kinds
    assert "activity" in kinds


def test_timeline_with_events_includes_pomodoro(conn):
    db.save_pomodoro(conn, _today_ts(9), 25, 5, 4)
    items = timeline.get_timeline_with_events(conn)
    assert any(it["type"] == "pomodoro" for it in items)


def test_group_into_sessions_empty():
    assert timeline.group_into_sessions([]) == []


def test_group_into_sessions_single_session():
    items = [{"ts": 1000}, {"ts": 1100}, {"ts": 1200}]
    sessions = timeline.group_into_sessions(items, gap_minutes=15)
    assert len(sessions) == 1
    assert sessions[0]["count"] == 3


def test_group_into_sessions_split():
    items = [{"ts": 1000}, {"ts": 1100}, {"ts": 5000}]
    sessions = timeline.group_into_sessions(items, gap_minutes=15)
    assert len(sessions) == 2


def test_format_ascii_empty(conn):
    out = timeline.format_timeline_ascii(conn)
    assert out == "(no activity)"


def test_format_ascii_basic(conn):
    _log(conn, _today_ts(10), "yt.com", "block")
    _log(conn, _today_ts(11), "gh.com", "allow")
    out = timeline.format_timeline_ascii(conn)
    assert "yt.com" in out
    assert "gh.com" in out
    assert "x" in out  # block marker


def test_format_ascii_with_focus(conn):
    db.save_focus_session(conn, _today_ts(9), 30, True)
    out = timeline.format_timeline_ascii(conn)
    assert "focus" in out


def test_get_timeline_verdict_preserved(conn):
    _log(conn, _today_ts(10), "yt.com", "block")
    items = timeline.get_timeline(conn)
    assert items[0]["verdict"] == "block"
