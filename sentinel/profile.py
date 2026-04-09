"""User work-style profile built from behavior."""
import json
import time
import datetime as _dt
from collections import Counter
from . import classifier, stats, patterns


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS profile (
        key TEXT PRIMARY KEY, value TEXT, updated_at REAL
    )""")


def _chronotype(by_hour: dict) -> str:
    if not by_hour:
        return "morning"
    buckets = {"morning": 0, "afternoon": 0, "evening": 0}
    for h, c in by_hour.items():
        if 5 <= int(h) < 12:
            buckets["morning"] += c
        elif 12 <= int(h) < 18:
            buckets["afternoon"] += c
        else:
            buckets["evening"] += c
    return max(buckets.items(), key=lambda kv: kv[1])[0]


def _work_days(conn, since: float) -> list:
    rows = conn.execute(
        "SELECT ts FROM activity_log WHERE ts>=? AND verdict='allow'", (since,)
    ).fetchall()
    names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    days = Counter()
    for r in rows:
        days[names[_dt.datetime.fromtimestamp(r["ts"]).weekday()]] += 1
    avg = (sum(days.values()) / 7) if days else 0
    return [d for d in names if days.get(d, 0) >= max(1, avg * 0.5)]


def _break_frequency(sessions: list) -> str:
    if len(sessions) < 2:
        return "low"
    if len(sessions) >= 8:
        return "high"
    if len(sessions) >= 4:
        return "medium"
    return "low"


def _compute(conn) -> dict:
    since = time.time() - 30 * 86400
    daily = patterns.find_daily_patterns(conn)
    prod_by_hour = daily["productive_by_hour"]
    sessions = patterns.find_work_sessions(conn)
    recent = [s for s in sessions if s["start"] >= since]
    avg_focus = (sum(s["duration_s"] for s in recent) / len(recent) / 60) if recent else 0
    streaks = [s["duration_s"] for s in recent]
    streak_avg = (sum(streaks) / len(streaks) / 60) if streaks else 0
    most_prod = max(prod_by_hour.items(), key=lambda kv: kv[1])[0] if prod_by_hour else 0
    top_distr = [d["domain"] for d in stats.get_top_distractions(conn, days=30, limit=5)]
    return {
        "chronotype": _chronotype(prod_by_hour),
        "focus_length_avg_min": round(avg_focus, 1),
        "most_productive_hour": int(most_prod),
        "top_distractions": top_distr,
        "streak_length_avg": round(streak_avg, 1),
        "work_days": _work_days(conn, since),
        "break_frequency": _break_frequency(recent),
    }


def update_profile(conn):
    _ensure_table(conn)
    p = _compute(conn)
    conn.execute(
        "INSERT OR REPLACE INTO profile (key, value, updated_at) VALUES (?, ?, ?)",
        ("profile", json.dumps(p), time.time()))
    conn.commit()
    return p


def get_profile(conn) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT value FROM profile WHERE key='profile'").fetchone()
    if not r:
        return _compute(conn)
    return json.loads(r["value"])


def compare_to_average(conn) -> dict:
    p = get_profile(conn)
    avgs = {"focus_length_avg_min": 25, "streak_length_avg": 30, "most_productive_hour": 10}
    return {
        "focus_vs_avg": round(p["focus_length_avg_min"] - avgs["focus_length_avg_min"], 1),
        "streak_vs_avg": round(p["streak_length_avg"] - avgs["streak_length_avg"], 1),
        "hour_shift": p["most_productive_hour"] - avgs["most_productive_hour"],
        "chronotype": p["chronotype"],
    }


async def describe_profile(conn, api_key: str) -> str:
    p = get_profile(conn)
    prompt = (
        f"Describe this user's work style in 3-4 sentences: {json.dumps(p)}. "
        "Be warm but specific."
    )
    return await classifier.call_gemini(api_key, prompt, max_tokens=200)
