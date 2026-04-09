"""Tests for sentinel.calendar_integrations."""
import pytest
import time
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock
from sentinel import calendar_integrations as ci, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


SAMPLE_ICAL = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Standup
DTSTART:20260409T140000Z
DTEND:20260409T143000Z
END:VEVENT
END:VCALENDAR"""


@pytest.mark.asyncio
async def test_fetch_google_calendar():
    mock_resp = MagicMock()
    mock_resp.text = SAMPLE_ICAL
    mock_resp.raise_for_status = MagicMock()
    with patch("sentinel.calendar_integrations.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        events = await ci.fetch_google_calendar("http://test/cal.ics")
        assert len(events) == 1


@pytest.mark.asyncio
async def test_fetch_error():
    with patch("sentinel.calendar_integrations.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=Exception("fail"))
        events = await ci.fetch_google_calendar("http://test/cal.ics")
        assert events == []


@pytest.mark.asyncio
async def test_fetch_outlook():
    mock_resp = MagicMock()
    mock_resp.text = SAMPLE_ICAL
    mock_resp.raise_for_status = MagicMock()
    with patch("sentinel.calendar_integrations.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        events = await ci.fetch_outlook_calendar("http://outlook/cal.ics")
        assert len(events) == 1


@pytest.mark.asyncio
async def test_fetch_calendly():
    mock_resp = MagicMock()
    mock_resp.text = SAMPLE_ICAL
    mock_resp.raise_for_status = MagicMock()
    with patch("sentinel.calendar_integrations.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        events = await ci.fetch_calendly("myusername")
        assert len(events) == 1


def test_get_meetings_today():
    now = time.time()
    today = datetime.now().date()
    today_ts = datetime.combine(today, datetime.min.time()).timestamp()
    events = [
        {"title": "Today", "start": today_ts + 3600, "end": today_ts + 7200},
        {"title": "Tomorrow", "start": today_ts + 86400 + 3600, "end": today_ts + 86400 + 7200},
    ]
    meetings = ci.get_meetings_today(events)
    assert len(meetings) == 1
    assert meetings[0]["title"] == "Today"


def test_get_meetings_today_empty():
    assert ci.get_meetings_today([]) == []


def test_get_free_blocks_empty_day():
    free = ci.get_free_blocks([])
    assert len(free) == 1  # Entire working day is free


def test_get_free_blocks_with_meetings():
    today = datetime.now().date()
    day_start = datetime.combine(today, datetime.min.time()).timestamp()
    events = [
        {"start": day_start + 10 * 3600, "end": day_start + 11 * 3600},  # 10-11am
    ]
    free = ci.get_free_blocks(events, hour_start=9, hour_end=17)
    # Should have 9-10am and 11am-5pm
    assert len(free) == 2


def test_get_free_blocks_overlapping():
    today = datetime.now().date()
    day_start = datetime.combine(today, datetime.min.time()).timestamp()
    events = [
        {"start": day_start + 10 * 3600, "end": day_start + 12 * 3600},
        {"start": day_start + 11 * 3600, "end": day_start + 13 * 3600},
    ]
    free = ci.get_free_blocks(events, hour_start=9, hour_end=17)
    # Should handle overlap, result in 9-10 and 13-17
    assert len(free) == 2


@pytest.mark.asyncio
async def test_auto_block_during_meetings(conn):
    today = datetime.now().date()
    today_ts = datetime.combine(today, datetime.min.time()).timestamp()
    with patch("sentinel.calendar_integrations.fetch_google_calendar",
               new_callable=AsyncMock, return_value=[
                   {"title": "Meeting", "start": today_ts + 3600, "end": today_ts + 7200}
               ]):
        count = await ci.auto_block_during_meetings(conn, "http://test/cal.ics")
        assert count == 1


def test_get_free_blocks_fully_booked():
    today = datetime.now().date()
    day_start = datetime.combine(today, datetime.min.time()).timestamp()
    events = [
        {"start": day_start + 9 * 3600, "end": day_start + 17 * 3600},
    ]
    free = ci.get_free_blocks(events, hour_start=9, hour_end=17)
    assert free == []
