"""Time-window primitive for rule activation.

Pomodoro and focus sessions used to live here. They're now expressible as
trigger recipes (kv counters + block_domain + log), so all of that code is
gone — only the time-window matcher survives because the blocking hot path
needs to know if a rule with a schedule is currently active.
"""
import datetime as _dt

_DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
         "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
         "friday": 4, "saturday": 5, "sunday": 6}


def parse_days(days_spec):
    if isinstance(days_spec, list):
        return {_DAYS[d.lower()] for d in days_spec if d.lower() in _DAYS}
    s = (days_spec or "").lower().strip()
    if not s or s == "all" or s == "everyday":
        return set(range(7))
    if "-" in s:
        a, b = s.split("-", 1)
        if a in _DAYS and b in _DAYS:
            i, j = _DAYS[a], _DAYS[b]
            return {k % 7 for k in range(i, i + (j - i) % 7 + 1)}
    return {_DAYS[p.strip()] for p in s.split(",") if p.strip() in _DAYS}


def _parse_hm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def is_schedule_active(schedule, now=None):
    if not schedule or "start" not in schedule or "end" not in schedule:
        return False
    now = now or _dt.datetime.now()
    days = parse_days(schedule.get("days", "all"))
    try:
        start, end = _parse_hm(schedule["start"]), _parse_hm(schedule["end"])
    except (ValueError, AttributeError):
        return False
    cur = now.hour * 60 + now.minute
    if start <= end:
        return now.weekday() in days and start <= cur < end
    # Crosses midnight: active if (today in days and cur >= start)
    # or (yesterday in days and cur < end)
    if cur >= start:
        return now.weekday() in days
    yesterday = (now.weekday() - 1) % 7
    return yesterday in days and cur < end
