"""Activity timeline — chronological view of what happened."""
import datetime as _dt
from . import db


def _day_bounds(date_str: str = None):
    if date_str:
        d = _dt.datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        d = _dt.date.today()
    start = _dt.datetime.combine(d, _dt.time.min).timestamp()
    end = _dt.datetime.combine(d, _dt.time.max).timestamp()
    return start, end


def get_timeline(conn, date_str: str = None) -> list:
    start, end = _day_bounds(date_str)
    rows = conn.execute(
        "SELECT ts, app, title, domain, verdict FROM activity_log "
        "WHERE ts BETWEEN ? AND ? ORDER BY ts", (start, end)).fetchall()
    return [{"type": "activity", "ts": r["ts"], "app": r["app"],
             "title": r["title"], "domain": r["domain"], "verdict": r["verdict"]}
            for r in rows]


def _focus_entries(conn, start, end):
    try:
        rows = conn.execute(
            "SELECT id, start_ts, duration_minutes, ended_at FROM focus_sessions "
            "WHERE start_ts BETWEEN ? AND ?", (start, end)).fetchall()
    except Exception:
        return []
    return [{"type": "focus_session", "ts": r["start_ts"],
             "duration_minutes": r["duration_minutes"], "ended_at": r["ended_at"]}
            for r in rows]


def _pomodoro_entries(conn, start, end):
    try:
        rows = conn.execute(
            "SELECT id, start_ts, work_minutes FROM pomodoro_sessions "
            "WHERE start_ts BETWEEN ? AND ?", (start, end)).fetchall()
    except Exception:
        return []
    return [{"type": "pomodoro", "ts": r["start_ts"], "work_minutes": r["work_minutes"]}
            for r in rows]


def get_timeline_with_events(conn, date_str: str = None) -> list:
    start, end = _day_bounds(date_str)
    items = get_timeline(conn, date_str)
    items += _focus_entries(conn, start, end)
    items += _pomodoro_entries(conn, start, end)
    return sorted(items, key=lambda x: x.get("ts") or 0)


def group_into_sessions(activities: list, gap_minutes: int = 15) -> list:
    if not activities:
        return []
    gap = gap_minutes * 60
    sessions = []
    cur = [activities[0]]
    for a in activities[1:]:
        if (a.get("ts") or 0) - (cur[-1].get("ts") or 0) <= gap:
            cur.append(a)
        else:
            sessions.append({"start": cur[0]["ts"], "end": cur[-1]["ts"],
                             "count": len(cur), "items": cur})
            cur = [a]
    sessions.append({"start": cur[0]["ts"], "end": cur[-1]["ts"],
                     "count": len(cur), "items": cur})
    return sessions


def format_timeline_ascii(conn, date_str: str = None) -> str:
    items = get_timeline_with_events(conn, date_str)
    if not items:
        return "(no activity)"
    lines = []
    for it in items:
        ts = it.get("ts") or 0
        clock = _dt.datetime.fromtimestamp(ts).strftime("%H:%M")
        t = it["type"]
        if t == "activity":
            label = it.get("domain") or it.get("app") or "?"
            mark = "x" if it.get("verdict") == "block" else "."
            lines.append(f"{clock} {mark} {label}")
        elif t == "focus_session":
            lines.append(f"{clock} * focus {it.get('duration_minutes', 0)}m")
        elif t == "pomodoro":
            lines.append(f"{clock} * pomodoro {it.get('work_minutes', 0)}m")
    return "\n".join(lines)
