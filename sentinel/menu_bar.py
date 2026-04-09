"""Menu bar integration hints — for a future SwiftUI menu bar app."""


def get_status_icon(state: str) -> str:
    """Emoji icon for menu bar state."""
    icons = {
        "focused": "🎯",
        "blocked": "🛑",
        "break": "☕",
        "idle": "⏸",
        "ok": "✓",
        "warning": "⚠",
        "error": "✗",
    }
    return icons.get(state, "○")


def get_status_summary(conn) -> dict:
    """Summary for menu bar display."""
    from . import db, stats as stats_mod
    score = stats_mod.calculate_score(conn)
    active_rules = sum(1 for r in db.get_rules(conn) if r.get("active"))
    blocked_now = 0
    try:
        from . import blocker
        blocked_now = len(blocker._blocked_domains)
    except Exception:
        pass
    state = "ok"
    if score < 50:
        state = "warning"
    elif score < 25:
        state = "error"
    return {
        "state": state,
        "icon": get_status_icon(state),
        "score": score,
        "active_rules": active_rules,
        "blocked": blocked_now,
        "summary": f"Score {score} • {active_rules} rules • {blocked_now} blocked",
    }


def get_menu_items(conn) -> list:
    """Menu items that should appear in the menu bar dropdown."""
    return [
        {"id": "status", "label": "Status", "shortcut": "⌘S"},
        {"id": "pomodoro", "label": "Start Pomodoro", "shortcut": "⌘P"},
        {"id": "focus", "label": "Start Focus Session", "shortcut": "⌘F"},
        {"id": "add_rule", "label": "Add Rule", "shortcut": "⌘R"},
        {"id": "report", "label": "Today's Report"},
        {"id": "separator"},
        {"id": "log_water", "label": "Log Water"},
        {"id": "log_mood", "label": "Log Mood"},
        {"id": "separator"},
        {"id": "settings", "label": "Settings", "shortcut": "⌘,"},
        {"id": "quit", "label": "Quit", "shortcut": "⌘Q"},
    ]


def get_notifications_summary(conn) -> list:
    """Notifications to show in menu bar."""
    from . import alerts
    alerts_list = alerts.get_alerts(conn) if hasattr(alerts, "get_alerts") else []
    return alerts_list[:5]


def format_menu_bar_title(conn) -> str:
    """Short title for the menu bar item itself."""
    summary = get_status_summary(conn)
    return f"{summary['icon']} {summary['score']}"
