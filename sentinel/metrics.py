"""Prometheus-compatible metrics endpoint."""
import time
from . import db


_start_time = time.time()


def _counter_line(name: str, value, labels: dict = None, help_text: str = "") -> str:
    """Format a single Prometheus line."""
    label_str = ""
    if labels:
        parts = [f'{k}="{v}"' for k, v in labels.items()]
        label_str = "{" + ",".join(parts) + "}"
    return f"{name}{label_str} {value}"


def collect_metrics(conn) -> str:
    """Return Prometheus-format metrics."""
    lines = []

    # Uptime
    lines.append("# HELP sentinel_uptime_seconds Server uptime")
    lines.append("# TYPE sentinel_uptime_seconds counter")
    lines.append(_counter_line("sentinel_uptime_seconds", int(time.time() - _start_time)))

    # Rule count
    rules = db.get_rules(conn, active_only=False)
    active = sum(1 for r in rules if r.get("active"))
    lines.append("# HELP sentinel_rules_total Total number of rules")
    lines.append("# TYPE sentinel_rules_total gauge")
    lines.append(_counter_line("sentinel_rules_total", len(rules)))
    lines.append(_counter_line("sentinel_rules_active", active))

    # Activity log
    activities = db.get_activities(conn, limit=10000)
    lines.append("# HELP sentinel_activities_total Activities logged")
    lines.append("# TYPE sentinel_activities_total counter")
    lines.append(_counter_line("sentinel_activities_total", len(activities)))

    # Blocked count
    blocked = sum(1 for a in activities if a.get("verdict") == "block")
    lines.append(_counter_line("sentinel_blocked_total", blocked))

    # Seen domains count
    r = conn.execute("SELECT COUNT(*) as c FROM seen_domains").fetchone()
    lines.append("# HELP sentinel_seen_domains_total Domains classified")
    lines.append("# TYPE sentinel_seen_domains_total gauge")
    lines.append(_counter_line("sentinel_seen_domains_total", r["c"] if r else 0))

    # By category
    for cat in ("streaming", "social", "adult", "gaming", "shopping", "none"):
        r = conn.execute("SELECT COUNT(*) as c FROM seen_domains WHERE category=?", (cat,)).fetchone()
        lines.append(_counter_line("sentinel_domains_by_category",
                                    r["c"] if r else 0, {"category": cat}))

    return "\n".join(lines) + "\n"


def get_uptime_seconds() -> int:
    return int(time.time() - _start_time)


def reset_uptime():
    global _start_time
    _start_time = time.time()
