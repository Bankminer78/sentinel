"""macOS widget data feed — for a future WidgetKit extension."""
from datetime import datetime
from . import db, stats as stats_mod


def small_widget_data(conn) -> dict:
    """Data for the small widget (square, minimal info)."""
    score = stats_mod.calculate_score(conn)
    return {
        "size": "small",
        "score": score,
        "label": f"{score}",
        "sub_label": "today",
        "color": "red" if score < 50 else "green",
    }


def medium_widget_data(conn) -> dict:
    """Data for the medium widget (2x1)."""
    score = stats_mod.calculate_score(conn)
    breakdown = stats_mod.get_daily_breakdown(conn)
    top = stats_mod.get_top_distractions(conn, days=1, limit=3)
    return {
        "size": "medium",
        "score": score,
        "top_distractions": [{"domain": d.get("domain"),
                               "seconds": d.get("seconds", 0)} for d in top],
        "breakdown": breakdown,
    }


def large_widget_data(conn) -> dict:
    """Data for the large widget (2x2)."""
    score = stats_mod.calculate_score(conn)
    breakdown = stats_mod.get_daily_breakdown(conn)
    week = stats_mod.get_week_summary(conn)
    top = stats_mod.get_top_distractions(conn, days=7, limit=5)
    rules_count = len(db.get_rules(conn))
    return {
        "size": "large",
        "score": score,
        "week_avg": week.get("avg_score") if isinstance(week, dict) else 0,
        "top_distractions": top,
        "breakdown": breakdown,
        "rules_count": rules_count,
    }


def lockscreen_widget_data(conn) -> dict:
    """Data for the iOS lockscreen widget (very tiny)."""
    score = stats_mod.calculate_score(conn)
    return {
        "size": "lockscreen",
        "text": f"Sentinel {score}",
    }


def dynamic_island_data(conn) -> dict:
    """iOS Dynamic Island live activity data."""
    from . import scheduler
    pomodoro = scheduler.get_pomodoro_state(conn)
    if pomodoro:
        return {
            "active": True,
            "state": pomodoro.get("state"),
            "seconds_remaining": pomodoro.get("seconds_remaining", 0),
            "label": "Pomodoro",
        }
    return {"active": False}


def refresh_interval_seconds() -> int:
    """How often should widgets refresh."""
    return 300  # 5 minutes
