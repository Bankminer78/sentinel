"""Calendar integration — auto-activate blocks during meetings."""
import re, time, httpx
from datetime import datetime


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS calendar_events (
        id INTEGER PRIMARY KEY, title TEXT, start_ts REAL, end_ts REAL,
        location TEXT, synced_at REAL
    )""")


def parse_ical(ical_text: str) -> list:
    """Parse ICS into events."""
    events = []
    current = {}
    in_event = False
    for line in ical_text.splitlines():
        line = line.strip()
        if line == "BEGIN:VEVENT":
            in_event = True
            current = {}
        elif line == "END:VEVENT":
            if in_event and "start" in current and "end" in current:
                events.append(current)
            in_event = False
        elif in_event:
            if line.startswith("SUMMARY:"):
                current["title"] = line[8:]
            elif line.startswith("DTSTART") and ":" in line:
                current["start"] = _parse_ical_time(line.split(":", 1)[1])
            elif line.startswith("DTEND") and ":" in line:
                current["end"] = _parse_ical_time(line.split(":", 1)[1])
            elif line.startswith("LOCATION:"):
                current["location"] = line[9:]
    return events


def _parse_ical_time(s: str) -> float:
    """Parse ICAL datetime."""
    s = s.strip().rstrip("Z")
    try:
        if "T" in s:
            return datetime.strptime(s, "%Y%m%dT%H%M%S").timestamp()
        return datetime.strptime(s, "%Y%m%d").timestamp()
    except Exception:
        return 0.0


def is_in_meeting(events: list, now=None) -> bool:
    t = now if now is not None else time.time()
    return any(e.get("start", 0) <= t <= e.get("end", 0) for e in events)


def get_current_event(events: list, now=None) -> dict:
    t = now if now is not None else time.time()
    for e in events:
        if e.get("start", 0) <= t <= e.get("end", 0):
            return e
    return None


async def fetch_ical_url(url: str) -> str:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.text


async def sync_calendar(conn, ical_url: str) -> int:
    _ensure_table(conn)
    text = await fetch_ical_url(ical_url)
    events = parse_ical(text)
    conn.execute("DELETE FROM calendar_events")
    now = time.time()
    for e in events:
        conn.execute(
            "INSERT INTO calendar_events (title, start_ts, end_ts, location, synced_at) VALUES (?, ?, ?, ?, ?)",
            (e.get("title", ""), e.get("start", 0), e.get("end", 0), e.get("location", ""), now))
    conn.commit()
    return len(events)


def get_cached_events(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute("SELECT * FROM calendar_events ORDER BY start_ts").fetchall()
    return [dict(r) for r in rows]
