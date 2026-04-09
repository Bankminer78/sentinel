"""Calendar integrations — Google Calendar, Outlook, Calendly via iCal."""
import httpx
from datetime import datetime, timedelta
from . import calendar


async def fetch_google_calendar(ical_url: str) -> list:
    """Fetch Google Calendar iCal."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(ical_url)
            r.raise_for_status()
            return calendar.parse_ical(r.text)
    except Exception:
        return []


async def fetch_outlook_calendar(ical_url: str) -> list:
    """Fetch Outlook iCal export."""
    return await fetch_google_calendar(ical_url)  # Same format


async def fetch_calendly(username: str) -> list:
    """Fetch Calendly events via their iCal."""
    url = f"https://calendly.com/{username}/ical"
    return await fetch_google_calendar(url)


def get_meetings_today(events: list) -> list:
    """Filter events to today only."""
    today = datetime.now().date()
    today_start = datetime.combine(today, datetime.min.time()).timestamp()
    today_end = today_start + 86400
    return [e for e in events
            if today_start <= e.get("start", 0) < today_end]


def get_free_blocks(events: list, hour_start: int = 9, hour_end: int = 17) -> list:
    """Find free time blocks during working hours today."""
    today = datetime.now().date()
    day_start = datetime.combine(today, datetime.min.time()).timestamp() + hour_start * 3600
    day_end = datetime.combine(today, datetime.min.time()).timestamp() + hour_end * 3600
    busy = sorted(
        [(e["start"], e["end"]) for e in events
         if e.get("start", 0) < day_end and e.get("end", 0) > day_start],
        key=lambda x: x[0])
    free = []
    cursor = day_start
    for s, e in busy:
        if s > cursor:
            free.append({"start": cursor, "end": min(s, day_end)})
        cursor = max(cursor, e)
    if cursor < day_end:
        free.append({"start": cursor, "end": day_end})
    return free


async def auto_block_during_meetings(conn, ical_url: str) -> int:
    """Fetch calendar, return count of meetings today."""
    events = await fetch_google_calendar(ical_url)
    today_meetings = get_meetings_today(events)
    return len(today_meetings)
