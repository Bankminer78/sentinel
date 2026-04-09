"""Screen time — track total screen usage from activity log."""
import time
from datetime import datetime, timedelta
from collections import Counter


def total_today(conn) -> float:
    """Total screen time today in hours."""
    today_start = datetime.combine(datetime.now().date(), datetime.min.time()).timestamp()
    try:
        rows = conn.execute(
            "SELECT duration_s FROM activity_log WHERE ts >= ?", (today_start,)).fetchall()
    except Exception:
        return 0
    total_s = sum(r["duration_s"] or 0 for r in rows)
    return round(total_s / 3600, 2)


def total_for_days(conn, days: int = 7) -> float:
    cutoff = time.time() - days * 86400
    try:
        rows = conn.execute(
            "SELECT duration_s FROM activity_log WHERE ts > ?", (cutoff,)).fetchall()
    except Exception:
        return 0
    total_s = sum(r["duration_s"] or 0 for r in rows)
    return round(total_s / 3600, 2)


def by_app_today(conn) -> dict:
    today_start = datetime.combine(datetime.now().date(), datetime.min.time()).timestamp()
    try:
        rows = conn.execute(
            "SELECT app, duration_s FROM activity_log WHERE ts >= ?", (today_start,)).fetchall()
    except Exception:
        return {}
    by_app = {}
    for r in rows:
        app = r["app"] or "unknown"
        by_app[app] = by_app.get(app, 0) + (r["duration_s"] or 0)
    return {k: round(v / 60, 1) for k, v in by_app.items()}  # minutes


def top_apps_today(conn, limit: int = 5) -> list:
    by_app = by_app_today(conn)
    sorted_apps = sorted(by_app.items(), key=lambda x: x[1], reverse=True)
    return [{"app": a, "minutes": m} for a, m in sorted_apps[:limit]]


def hourly_usage(conn, date_str: str = None) -> dict:
    """Return {hour: minutes} for a specific day."""
    d = date_str or datetime.now().strftime("%Y-%m-%d")
    start = datetime.strptime(d, "%Y-%m-%d").timestamp()
    end = start + 86400
    try:
        rows = conn.execute(
            "SELECT ts, duration_s FROM activity_log WHERE ts >= ? AND ts < ?",
            (start, end)).fetchall()
    except Exception:
        return {}
    hours = {h: 0 for h in range(24)}
    for r in rows:
        h = datetime.fromtimestamp(r["ts"]).hour
        hours[h] += (r["duration_s"] or 0) / 60
    return {str(k): round(v, 1) for k, v in hours.items()}


def weekly_average_hours(conn) -> float:
    total = total_for_days(conn, days=7)
    return round(total / 7, 1)


def compare_to_yesterday(conn) -> dict:
    today_start = datetime.combine(datetime.now().date(), datetime.min.time()).timestamp()
    yesterday_start = today_start - 86400
    try:
        today_r = conn.execute(
            "SELECT COALESCE(SUM(duration_s), 0) as total FROM activity_log WHERE ts >= ?",
            (today_start,)).fetchone()
        yesterday_r = conn.execute(
            "SELECT COALESCE(SUM(duration_s), 0) as total FROM activity_log WHERE ts >= ? AND ts < ?",
            (yesterday_start, today_start)).fetchone()
    except Exception:
        return {"today": 0, "yesterday": 0, "diff": 0}
    today_h = (today_r["total"] or 0) / 3600
    yesterday_h = (yesterday_r["total"] or 0) / 3600
    return {
        "today": round(today_h, 2),
        "yesterday": round(yesterday_h, 2),
        "diff": round(today_h - yesterday_h, 2),
    }


def target_tracker(conn, target_hours: float) -> dict:
    current = total_today(conn)
    return {
        "target": target_hours,
        "current": current,
        "remaining": max(0, target_hours - current),
        "exceeded": current > target_hours,
    }


def longest_session_today(conn) -> float:
    today_start = datetime.combine(datetime.now().date(), datetime.min.time()).timestamp()
    try:
        r = conn.execute(
            "SELECT MAX(duration_s) as max FROM activity_log WHERE ts >= ?",
            (today_start,)).fetchone()
    except Exception:
        return 0
    return round((r["max"] or 0) / 60, 1)  # minutes
