"""Environment configuration — timezone, working hours, rest days, focus windows."""
import json
import datetime as _dt
from . import db

_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _now(now):
    return now or _dt.datetime.now()


def _parse_hm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _in_window(now, start, end):
    cur = now.hour * 60 + now.minute
    s, e = _parse_hm(start), _parse_hm(end)
    if s <= e:
        return s <= cur < e
    return cur >= s or cur < e


def set_timezone(conn, tz: str):
    db.set_config(conn, "env_timezone", tz)


def get_timezone(conn) -> str:
    return db.get_config(conn, "env_timezone", "UTC")


def set_working_hours(conn, start: str, end: str, days: list):
    db.set_config(conn, "env_working_hours",
                  json.dumps({"start": start, "end": end, "days": [d.lower() for d in days]}))


def get_working_hours(conn) -> dict:
    v = db.get_config(conn, "env_working_hours")
    if not v:
        return {"start": "09:00", "end": "17:00",
                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"]}
    return json.loads(v)


def is_working_hours(conn, now=None) -> bool:
    now = _now(now)
    wh = get_working_hours(conn)
    day = _DAYS[now.weekday()]
    if day not in wh["days"]:
        return False
    return _in_window(now, wh["start"], wh["end"])


def set_rest_days(conn, days: list):
    db.set_config(conn, "env_rest_days", json.dumps([d.lower() for d in days]))


def get_rest_days(conn) -> list:
    v = db.get_config(conn, "env_rest_days")
    return json.loads(v) if v else ["saturday", "sunday"]


def is_rest_day(conn, now=None) -> bool:
    now = _now(now)
    return _DAYS[now.weekday()] in get_rest_days(conn)


def set_focus_window(conn, start: str, end: str):
    db.set_config(conn, "env_focus_window", json.dumps({"start": start, "end": end}))


def get_focus_window(conn) -> dict:
    v = db.get_config(conn, "env_focus_window")
    return json.loads(v) if v else None


def is_focus_window(conn, now=None) -> bool:
    fw = get_focus_window(conn)
    if not fw:
        return False
    return _in_window(_now(now), fw["start"], fw["end"])


def get_environment(conn) -> dict:
    return {
        "timezone": get_timezone(conn),
        "working_hours": get_working_hours(conn),
        "rest_days": get_rest_days(conn),
        "focus_window": get_focus_window(conn),
    }
