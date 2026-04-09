"""Tests for sentinel.calendar."""
import pytest
import time
from unittest.mock import patch, AsyncMock, MagicMock
from sentinel import calendar, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


SAMPLE_ICAL = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Team Meeting
DTSTART:20260409T140000Z
DTEND:20260409T150000Z
LOCATION:Zoom
END:VEVENT
BEGIN:VEVENT
SUMMARY:1:1 with Alice
DTSTART:20260410T100000Z
DTEND:20260410T103000Z
END:VEVENT
END:VCALENDAR"""


def test_parse_ical_basic():
    events = calendar.parse_ical(SAMPLE_ICAL)
    assert len(events) == 2


def test_parse_ical_titles():
    events = calendar.parse_ical(SAMPLE_ICAL)
    titles = [e["title"] for e in events]
    assert "Team Meeting" in titles
    assert "1:1 with Alice" in titles


def test_parse_ical_empty():
    assert calendar.parse_ical("") == []


def test_parse_ical_malformed():
    malformed = "BEGIN:VEVENT\nSUMMARY:Broken\n"  # Missing END
    assert calendar.parse_ical(malformed) == []


def test_parse_ical_location():
    events = calendar.parse_ical(SAMPLE_ICAL)
    e1 = events[0]
    assert e1.get("location") == "Zoom"


def test_parse_ical_times():
    events = calendar.parse_ical(SAMPLE_ICAL)
    e1 = events[0]
    assert e1["start"] > 0
    assert e1["end"] > e1["start"]


def test_is_in_meeting_true():
    events = [{"start": 100.0, "end": 200.0, "title": "T"}]
    assert calendar.is_in_meeting(events, now=150.0) is True


def test_is_in_meeting_false():
    events = [{"start": 100.0, "end": 200.0, "title": "T"}]
    assert calendar.is_in_meeting(events, now=300.0) is False


def test_is_in_meeting_empty():
    assert calendar.is_in_meeting([], now=time.time()) is False


def test_get_current_event():
    events = [
        {"start": 100.0, "end": 200.0, "title": "Meeting 1"},
        {"start": 300.0, "end": 400.0, "title": "Meeting 2"},
    ]
    current = calendar.get_current_event(events, now=150.0)
    assert current["title"] == "Meeting 1"


def test_get_current_event_none():
    events = [{"start": 100.0, "end": 200.0, "title": "T"}]
    assert calendar.get_current_event(events, now=250.0) is None


@pytest.mark.asyncio
async def test_sync_calendar(conn):
    with patch("sentinel.calendar.fetch_ical_url", new_callable=AsyncMock, return_value=SAMPLE_ICAL):
        count = await calendar.sync_calendar(conn, "http://test.com/cal.ics")
        assert count == 2


@pytest.mark.asyncio
async def test_get_cached_events(conn):
    with patch("sentinel.calendar.fetch_ical_url", new_callable=AsyncMock, return_value=SAMPLE_ICAL):
        await calendar.sync_calendar(conn, "http://test.com/cal.ics")
    events = calendar.get_cached_events(conn)
    assert len(events) == 2


def test_cached_events_empty(conn):
    assert calendar.get_cached_events(conn) == []


def test_parse_ical_no_end_time():
    ical = """BEGIN:VEVENT
SUMMARY:NoEnd
DTSTART:20260409T140000Z
END:VEVENT"""
    events = calendar.parse_ical(ical)
    assert events == []  # Missing end time → excluded
