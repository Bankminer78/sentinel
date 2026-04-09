"""Tests for sentinel.profile."""
import time
import datetime as _dt
from unittest.mock import AsyncMock, patch
import pytest

from sentinel import profile


def _log(conn, ts, domain, verdict, duration=60):
    conn.execute(
        "INSERT INTO activity_log (ts, app, title, url, domain, verdict, duration_s) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ts, "app", "t", f"https://{domain}", domain, verdict, duration))
    conn.commit()


def test_get_profile_empty(conn):
    p = profile.get_profile(conn)
    assert "chronotype" in p
    assert "focus_length_avg_min" in p
    assert "most_productive_hour" in p


def test_get_profile_has_all_keys(conn):
    p = profile.get_profile(conn)
    for k in ("chronotype", "focus_length_avg_min", "most_productive_hour",
              "top_distractions", "streak_length_avg", "work_days", "break_frequency"):
        assert k in p


def test_update_profile_persists(conn):
    p = profile.update_profile(conn)
    r = conn.execute("SELECT value FROM profile WHERE key='profile'").fetchone()
    assert r is not None


def test_chronotype_morning(conn):
    base = _dt.datetime.now().replace(hour=8, minute=0, second=0, microsecond=0).timestamp()
    for i in range(5):
        _log(conn, base + i, "work.com", "allow")
    p = profile.update_profile(conn)
    assert p["chronotype"] == "morning"


def test_chronotype_evening(conn):
    base = _dt.datetime.now().replace(hour=22, minute=0, second=0, microsecond=0).timestamp()
    for i in range(5):
        _log(conn, base + i, "work.com", "allow")
    p = profile.update_profile(conn)
    assert p["chronotype"] == "evening"


def test_chronotype_afternoon(conn):
    base = _dt.datetime.now().replace(hour=14, minute=0, second=0, microsecond=0).timestamp()
    for i in range(5):
        _log(conn, base + i, "work.com", "allow")
    p = profile.update_profile(conn)
    assert p["chronotype"] == "afternoon"


def test_focus_length_positive(conn):
    now = time.time()
    for i in range(5):
        _log(conn, now + i * 30, "work.com", "allow")
    p = profile.update_profile(conn)
    assert p["focus_length_avg_min"] >= 0


def test_top_distractions_empty(conn):
    p = profile.update_profile(conn)
    assert p["top_distractions"] == []


def test_top_distractions_populated(conn):
    conn.execute("INSERT INTO seen_domains (domain, category, first_seen) VALUES (?, ?, ?)",
                 ("yt.com", "social", time.time()))
    conn.commit()
    _log(conn, time.time(), "yt.com", "block", duration=500)
    p = profile.update_profile(conn)
    assert "yt.com" in p["top_distractions"]


def test_work_days_weekday(conn):
    # Use last Monday at noon
    today = _dt.date.today()
    monday = today - _dt.timedelta(days=today.weekday())
    ts = _dt.datetime.combine(monday, _dt.time(12, 0)).timestamp()
    for i in range(3):
        _log(conn, ts + i, "work.com", "allow")
    p = profile.update_profile(conn)
    assert "mon" in p["work_days"]


def test_compare_to_average(conn):
    c = profile.compare_to_average(conn)
    assert "focus_vs_avg" in c
    assert "streak_vs_avg" in c
    assert "hour_shift" in c
    assert "chronotype" in c


def test_update_profile_returns_dict(conn):
    p = profile.update_profile(conn)
    assert isinstance(p, dict)


def test_break_frequency_low(conn):
    p = profile.update_profile(conn)
    assert p["break_frequency"] == "low"


def test_get_profile_after_update(conn):
    profile.update_profile(conn)
    p = profile.get_profile(conn)
    assert isinstance(p, dict)


@pytest.mark.asyncio
async def test_describe_profile(conn):
    with patch("sentinel.profile.classifier.call_gemini",
               new_callable=AsyncMock, return_value="You are a morning person."):
        r = await profile.describe_profile(conn, "fake-key")
        assert "morning" in r
