"""iCal export — focus sessions, pomodoros, scheduled blocks as calendar events."""
import json, time
from datetime import datetime, timezone
from . import db


def _ts_to_ical(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _escape(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def format_ical_event(uid: str, summary: str, start_ts: float,
                      end_ts: float, description: str = "") -> str:
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_ts_to_ical(time.time())}",
        f"DTSTART:{_ts_to_ical(start_ts)}",
        f"DTEND:{_ts_to_ical(end_ts)}",
        f"SUMMARY:{_escape(summary)}",
    ]
    if description:
        lines.append(f"DESCRIPTION:{_escape(description)}")
    lines.append("END:VEVENT")
    return "\r\n".join(lines)


def _wrap(body_events: list[str]) -> str:
    header = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Sentinel//EN"]
    return "\r\n".join(header + body_events + ["END:VCALENDAR"]) + "\r\n"


def focus_sessions_to_ical(conn) -> str:
    rows = conn.execute("SELECT * FROM focus_sessions ORDER BY start_ts").fetchall()
    events = []
    for r in rows:
        r = dict(r)
        start = r["start_ts"]
        end = r["ended_at"] or (start + (r["duration_minutes"] or 0) * 60)
        events.append(format_ical_event(
            f"focus-{r['id']}@sentinel", f"Focus Session ({r['duration_minutes']}m)",
            start, end, "Sentinel focus session"))
    return _wrap(events)


def pomodoros_to_ical(conn, days: int = 30) -> str:
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT * FROM pomodoro_sessions WHERE start_ts>? ORDER BY start_ts",
        (cutoff,)).fetchall()
    events = []
    for r in rows:
        r = dict(r)
        start = r["start_ts"]
        dur = (r["work_minutes"] + r["break_minutes"]) * r["total_cycles"] * 60
        end = r["ended_at"] or (start + dur)
        events.append(format_ical_event(
            f"pomo-{r['id']}@sentinel",
            f"Pomodoro x{r['total_cycles']}", start, end,
            f"Work {r['work_minutes']}m / Break {r['break_minutes']}m"))
    return _wrap(events)


def _next_occurrence_today(schedule: dict) -> tuple[float, float] | None:
    try:
        sh, sm = schedule["start"].split(":")
        eh, em = schedule["end"].split(":")
    except Exception:
        return None
    now = datetime.now()
    start = now.replace(hour=int(sh), minute=int(sm), second=0, microsecond=0)
    end = now.replace(hour=int(eh), minute=int(em), second=0, microsecond=0)
    if end <= start:
        end = end.replace(day=end.day + 1) if end.day < 28 else end
    return start.timestamp(), end.timestamp()


def blocks_to_ical(conn) -> str:
    rows = db.get_rules(conn, active_only=True)
    events = []
    for r in rows:
        parsed = json.loads(r.get("parsed") or "{}")
        sched = parsed.get("schedule")
        if not sched or "start" not in sched or "end" not in sched:
            continue
        window = _next_occurrence_today(sched)
        if not window:
            continue
        s, e = window
        events.append(format_ical_event(
            f"rule-{r['id']}@sentinel", f"Block: {r['text']}", s, e,
            f"Scheduled block rule #{r['id']}"))
    return _wrap(events)


def full_calendar_export(conn) -> str:
    def _body(ical: str) -> list[str]:
        lines = ical.split("\r\n")
        out, in_evt = [], False
        for ln in lines:
            if ln == "BEGIN:VEVENT":
                in_evt = True
            if in_evt:
                out.append(ln)
            if ln == "END:VEVENT":
                in_evt = False
        return out
    events = _body(focus_sessions_to_ical(conn)) + _body(pomodoros_to_ical(conn)) + _body(blocks_to_ical(conn))
    return _wrap(events)
