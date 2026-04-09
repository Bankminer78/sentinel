"""Tests for sentinel.reports."""
import pytest
import time
import json
from datetime import datetime
from unittest.mock import patch, AsyncMock
from sentinel import reports, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


@pytest.mark.asyncio
async def test_daily_report():
    import sqlite3
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE activity_log (id INTEGER PRIMARY KEY, ts REAL, app TEXT, title TEXT, url TEXT, domain TEXT, verdict TEXT, rule_id INTEGER, duration_s REAL DEFAULT 0);
        CREATE TABLE seen_domains (domain TEXT PRIMARY KEY, category TEXT, first_seen REAL);
    """)
    with patch("sentinel.reports.classifier.call_gemini", new_callable=AsyncMock,
               return_value="You had a productive day!"):
        result = await reports.daily_report(c, "key")
        assert "productive" in result.lower()
    c.close()


@pytest.mark.asyncio
async def test_daily_report_error():
    import sqlite3
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE activity_log (id INTEGER PRIMARY KEY, ts REAL, app TEXT, title TEXT, url TEXT, domain TEXT, verdict TEXT, rule_id INTEGER, duration_s REAL DEFAULT 0);
        CREATE TABLE seen_domains (domain TEXT PRIMARY KEY, category TEXT, first_seen REAL);
    """)
    with patch("sentinel.reports.classifier.call_gemini", new_callable=AsyncMock,
               side_effect=Exception("fail")):
        result = await reports.daily_report(c, "key")
        assert "score" in result.lower() or "stats" in result.lower()
    c.close()


@pytest.mark.asyncio
async def test_weekly_insights():
    import sqlite3
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE activity_log (id INTEGER PRIMARY KEY, ts REAL, app TEXT, title TEXT, url TEXT, domain TEXT, verdict TEXT, rule_id INTEGER, duration_s REAL DEFAULT 0);
        CREATE TABLE seen_domains (domain TEXT PRIMARY KEY, category TEXT, first_seen REAL);
    """)
    with patch("sentinel.reports.classifier.call_gemini", new_callable=AsyncMock,
               return_value='{"summary": "good week", "patterns": ["works mornings"], "recommendations": ["keep it up"]}'):
        result = await reports.weekly_insights(c, "key")
        assert result["summary"] == "good week"
        assert len(result["patterns"]) == 1
        assert len(result["recommendations"]) == 1
    c.close()


@pytest.mark.asyncio
async def test_weekly_insights_markdown_fence():
    import sqlite3
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE activity_log (id INTEGER PRIMARY KEY, ts REAL, app TEXT, title TEXT, url TEXT, domain TEXT, verdict TEXT, rule_id INTEGER, duration_s REAL DEFAULT 0);
        CREATE TABLE seen_domains (domain TEXT PRIMARY KEY, category TEXT, first_seen REAL);
    """)
    with patch("sentinel.reports.classifier.call_gemini", new_callable=AsyncMock,
               return_value='```json\n{"summary": "ok", "patterns": [], "recommendations": []}\n```'):
        result = await reports.weekly_insights(c, "key")
        assert result["summary"] == "ok"
    c.close()


@pytest.mark.asyncio
async def test_weekly_insights_error():
    import sqlite3
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE activity_log (id INTEGER PRIMARY KEY, ts REAL, app TEXT, title TEXT, url TEXT, domain TEXT, verdict TEXT, rule_id INTEGER, duration_s REAL DEFAULT 0);
        CREATE TABLE seen_domains (domain TEXT PRIMARY KEY, category TEXT, first_seen REAL);
    """)
    with patch("sentinel.reports.classifier.call_gemini", new_callable=AsyncMock,
               side_effect=Exception("fail")):
        result = await reports.weekly_insights(c, "key")
        assert "summary" in result
    c.close()


def test_time_distribution_empty(conn):
    dist = reports.time_distribution(conn)
    assert len(dist) == 24
    assert all(v == 0 for v in dist.values())


def test_time_distribution_with_data(conn):
    db.log_activity(conn, "App", "T", "", "test.com", "allow")
    # Manually set duration
    conn.execute("UPDATE activity_log SET duration_s=?", (60,))
    conn.commit()
    dist = reports.time_distribution(conn)
    total = sum(dist.values())
    assert total == 60


def test_peak_focus_hours_empty(conn):
    assert reports.peak_focus_hours(conn) == []


def test_peak_focus_hours_with_data(conn):
    db.save_seen(conn, "github.com", "none")
    for i in range(5):
        db.log_activity(conn, "", "", "", "github.com", "allow")
    hours = reports.peak_focus_hours(conn)
    assert len(hours) > 0


def test_distraction_triggers_empty(conn):
    assert reports.distraction_triggers(conn) == []


def test_distraction_triggers_with_data(conn):
    db.save_seen(conn, "youtube.com", "social")
    db.log_activity(conn, "Chrome", "", "", "github.com", "allow")
    db.log_activity(conn, "Chrome", "", "", "youtube.com", "allow")
    triggers = reports.distraction_triggers(conn)
    # Should find github -> youtube pattern
    assert any(t["distraction"] == "youtube.com" for t in triggers)


def test_time_distribution_has_all_hours(conn):
    dist = reports.time_distribution(conn)
    for h in range(24):
        assert str(h) in dist
