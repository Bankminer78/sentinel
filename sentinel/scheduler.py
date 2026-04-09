"""Scheduler — time-based rules, pomodoro, allowances, focus sessions."""
import datetime as _dt
from sentinel import db

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
    # crosses midnight: active if (today in days and cur >= start) or (yesterday in days and cur < end)
    if cur >= start:
        return now.weekday() in days
    yesterday = (now.weekday() - 1) % 7
    return yesterday in days and cur < end

# --- Pomodoro ---
def start_pomodoro(conn, work_minutes=25, break_minutes=5, cycles=4):
    now = _dt.datetime.now()
    pid = db.save_pomodoro(conn, now.timestamp(), work_minutes, break_minutes, cycles)
    ends_at = now + _dt.timedelta(minutes=work_minutes)
    return {"id": pid, "state": "work", "ends_at": ends_at.timestamp()}

def get_pomodoro_state(conn, now=None):
    p = db.get_active_pomodoro(conn)
    if not p:
        return None
    now = now or _dt.datetime.now()
    elapsed = now.timestamp() - p["start_ts"]
    cycle_len = (p["work_minutes"] + p["break_minutes"]) * 60
    full_duration = cycle_len * p["total_cycles"]
    if elapsed >= full_duration:
        db.update_pomodoro(conn, p["id"], state="done", ended_at=now.timestamp())
        return {"state": "done", "cycle": p["total_cycles"], "ends_at": p["start_ts"] + full_duration, "seconds_remaining": 0}
    cycle_idx = int(elapsed // cycle_len)
    within = elapsed - cycle_idx * cycle_len
    work_sec = p["work_minutes"] * 60
    if within < work_sec:
        state = "work"
        ends_at = p["start_ts"] + cycle_idx * cycle_len + work_sec
    else:
        state = "break"
        ends_at = p["start_ts"] + (cycle_idx + 1) * cycle_len
    return {"state": state, "cycle": cycle_idx + 1, "ends_at": ends_at,
            "seconds_remaining": int(ends_at - now.timestamp())}

def stop_pomodoro(conn):
    p = db.get_active_pomodoro(conn)
    if p:
        db.update_pomodoro(conn, p["id"], state="cancelled", ended_at=_dt.datetime.now().timestamp())

# --- Allowances ---
def record_allowance_use(conn, rule_id, seconds, now=None):
    d = (now or _dt.datetime.now()).strftime("%Y-%m-%d")
    db.add_allowance_use(conn, rule_id, d, seconds)

def get_allowance_remaining(conn, rule_id, daily_limit_seconds, now=None):
    d = (now or _dt.datetime.now()).strftime("%Y-%m-%d")
    used = db.get_allowance_used(conn, rule_id, d)
    return max(0, daily_limit_seconds - used)

# --- Focus sessions ---
def start_focus_session(conn, duration_minutes, locked=True):
    now = _dt.datetime.now()
    sid = db.save_focus_session(conn, now.timestamp(), duration_minutes, locked)
    ends_at = now + _dt.timedelta(minutes=duration_minutes)
    return {"id": sid, "locked": locked, "ends_at": ends_at.timestamp()}

def get_focus_session(conn, now=None):
    s = db.get_active_focus(conn)
    if not s:
        return None
    now = now or _dt.datetime.now()
    ends_at = s["start_ts"] + s["duration_minutes"] * 60
    if now.timestamp() >= ends_at:
        db.end_focus(conn, s["id"], ends_at)
        return None
    return {"id": s["id"], "locked": bool(s["locked"]), "ends_at": ends_at,
            "seconds_remaining": int(ends_at - now.timestamp())}

def end_focus_session(conn, session_id, force=False):
    s = db.get_active_focus(conn)
    if not s or s["id"] != session_id:
        return False
    if s["locked"] and not force:
        ends_at = s["start_ts"] + s["duration_minutes"] * 60
        if _dt.datetime.now().timestamp() < ends_at:
            return False
    db.end_focus(conn, session_id, _dt.datetime.now().timestamp())
    return True
