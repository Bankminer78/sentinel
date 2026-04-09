"""GitHub-style activity heatmap."""
from datetime import datetime, timedelta
from collections import Counter


def activity_heatmap_data(conn, days: int = 365) -> dict:
    """Return {date: count} for the past N days."""
    import time
    cutoff = time.time() - days * 86400
    try:
        rows = conn.execute(
            "SELECT ts FROM activity_log WHERE ts > ?", (cutoff,)).fetchall()
    except Exception:
        return {}
    counts = Counter()
    for r in rows:
        day = datetime.fromtimestamp(r["ts"]).strftime("%Y-%m-%d")
        counts[day] += 1
    return dict(counts)


def score_heatmap_data(conn, days: int = 365) -> dict:
    """Return {date: score} for productivity scores."""
    try:
        from . import stats as stats_mod
    except Exception:
        return {}
    today = datetime.now().date()
    result = {}
    for i in range(days):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        try:
            result[d] = stats_mod.calculate_score(conn, d)
        except Exception:
            result[d] = 0
    return result


def render_heatmap_ascii(data: dict, weeks: int = 52) -> str:
    """Render a heatmap as ASCII art."""
    if not data:
        return "(no data)"
    chars = " ░▒▓█"
    values = list(data.values())
    max_v = max(values) if values else 1
    today = datetime.now().date()
    days = sorted(data.keys(), reverse=True)[:weeks * 7]
    # Build 7 rows x N cols grid (day of week x week)
    grid = [["" for _ in range(weeks)] for _ in range(7)]
    for d_str in days:
        try:
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
            days_ago = (today - d).days
            week = days_ago // 7
            dow = d.weekday()
            if week < weeks:
                v = data[d_str]
                idx = int((v / max_v) * (len(chars) - 1)) if max_v > 0 else 0
                grid[dow][weeks - 1 - week] = chars[idx]
        except Exception:
            pass
    # Fill empty cells
    for row in grid:
        for i in range(len(row)):
            if not row[i]:
                row[i] = chars[0]
    lines = []
    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for i, row in enumerate(grid):
        lines.append(f"{day_labels[i]} " + "".join(row))
    return "\n".join(lines)


def render_html_heatmap(data: dict, title: str = "Activity") -> str:
    """Render a heatmap as minimal HTML."""
    if not data:
        return f"<div>{title}: no data</div>"
    values = list(data.values())
    max_v = max(values) if values else 1
    html = f'<div class="heatmap"><h3>{title}</h3><div class="cells">'
    for d, v in sorted(data.items(), reverse=True)[:365]:
        intensity = int((v / max_v) * 9) if max_v > 0 else 0
        color = f"#0{intensity}0{intensity}00" if intensity > 0 else "#222"
        html += f'<span class="cell" title="{d}: {v}" style="background:{color};width:10px;height:10px;display:inline-block;margin:1px"></span>'
    html += "</div></div>"
    return html


def stats_for_heatmap(data: dict) -> dict:
    if not data:
        return {"total": 0, "avg": 0, "max": 0, "days_active": 0}
    values = list(data.values())
    return {
        "total": sum(values),
        "avg": round(sum(values) / len(values), 1),
        "max": max(values),
        "days_active": sum(1 for v in values if v > 0),
    }
