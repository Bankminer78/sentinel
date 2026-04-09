"""Tests for sentinel.alerts."""
import time
import datetime as _dt
from unittest.mock import AsyncMock, patch
import pytest

from sentinel import alerts, habits


def _log(conn, ts, domain, verdict, duration=60):
    conn.execute(
        "INSERT INTO activity_log (ts, app, title, url, domain, verdict, duration_s) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ts, "app", "t", f"https://{domain}", domain, verdict, duration))
    conn.commit()


def _set_category(conn, domain, category):
    conn.execute(
        "INSERT OR REPLACE INTO seen_domains (domain, category, first_seen) VALUES (?, ?, ?)",
        (domain, category, time.time()))
    conn.commit()


def test_create_alert(conn):
    aid = alerts.create_alert(conn, "low score", "score_below", 50.0, "notify")
    assert aid > 0


def test_get_alerts_empty(conn):
    assert alerts.get_alerts(conn) == []


def test_get_alerts(conn):
    alerts.create_alert(conn, "a1", "score_below", 50.0)
    alerts.create_alert(conn, "a2", "time_spent_over", 3600)
    assert len(alerts.get_alerts(conn)) == 2


def test_delete_alert(conn):
    aid = alerts.create_alert(conn, "temp", "score_below", 50.0)
    alerts.delete_alert(conn, aid)
    assert alerts.get_alerts(conn) == []


def test_mute_alert(conn):
    aid = alerts.create_alert(conn, "m", "score_below", 50.0)
    alerts.mute_alert(conn, aid, 10)
    a = alerts.get_alerts(conn)[0]
    assert a["muted_until"] > time.time()


@pytest.mark.asyncio
async def test_check_alerts_empty(conn):
    r = await alerts.check_alerts(conn)
    assert r == []


@pytest.mark.asyncio
async def test_check_alerts_score_below_triggers(conn):
    _set_category(conn, "yt.com", "social")
    _log(conn, time.time(), "yt.com", "block", duration=600)
    alerts.create_alert(conn, "low", "score_below", 50.0)
    r = await alerts.check_alerts(conn)
    assert len(r) == 1
    assert r[0]["name"] == "low"


@pytest.mark.asyncio
async def test_check_alerts_score_below_not_triggered(conn):
    _log(conn, time.time(), "work.com", "allow", duration=600)
    alerts.create_alert(conn, "low", "score_below", 50.0)
    r = await alerts.check_alerts(conn)
    assert r == []


@pytest.mark.asyncio
async def test_check_alerts_time_spent_over(conn):
    _set_category(conn, "yt.com", "social")
    _log(conn, time.time(), "yt.com", "block", duration=3600)
    alerts.create_alert(conn, "t", "time_spent_over", 1000)
    r = await alerts.check_alerts(conn)
    assert len(r) == 1


@pytest.mark.asyncio
async def test_check_alerts_time_spent_not_over(conn):
    _set_category(conn, "yt.com", "social")
    _log(conn, time.time(), "yt.com", "block", duration=500)
    alerts.create_alert(conn, "t", "time_spent_over", 1000)
    r = await alerts.check_alerts(conn)
    assert r == []


@pytest.mark.asyncio
async def test_check_alerts_muted(conn):
    _set_category(conn, "yt.com", "social")
    _log(conn, time.time(), "yt.com", "block", duration=3600)
    aid = alerts.create_alert(conn, "t", "time_spent_over", 100)
    alerts.mute_alert(conn, aid, 60)
    r = await alerts.check_alerts(conn)
    assert r == []


@pytest.mark.asyncio
async def test_check_alerts_streak_about_to_break(conn):
    hid = habits.add_habit(conn, "read")
    today = _dt.date.today()
    for i in range(1, 4):
        habits.log_habit(conn, hid, (today - _dt.timedelta(days=i)).isoformat())
    alerts.create_alert(conn, "streak", "streak_about_to_break", 2)
    r = await alerts.check_alerts(conn)
    assert len(r) == 1


@pytest.mark.asyncio
async def test_check_alerts_unknown_condition(conn):
    alerts.create_alert(conn, "u", "unknown_cond", 10)
    r = await alerts.check_alerts(conn)
    assert r == []


def test_alert_has_action(conn):
    alerts.create_alert(conn, "a", "score_below", 10, "email")
    a = alerts.get_alerts(conn)[0]
    assert a["action"] == "email"


def test_delete_missing_alert(conn):
    alerts.delete_alert(conn, 999)  # should not raise
    assert alerts.get_alerts(conn) == []
