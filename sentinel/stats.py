"""Views over the activity log — score, breakdown, top distractions.

Goals and streaks used to live here. They're now expressible as triggers
(kv_increment + when + block_domain), so the hardcoded implementations are
gone. The remaining functions are the ones the /stats endpoint and the UI
actually call.
"""
import time
from datetime import datetime, timedelta

DISTRACTING = {"streaming", "social", "adult", "gaming", "shopping"}


def _day_bounds(date_str=None):
    d = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now().replace(
        hour=0, minute=0, second=0, microsecond=0)
    start = d.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    return start, start + 86400


def _categorize(conn, domain):
    if not domain:
        return "neutral"
    r = conn.execute("SELECT category FROM seen_domains WHERE domain=?", (domain,)).fetchone()
    cat = r["category"] if r else None
    return "distracting" if cat in DISTRACTING else "productive"


def get_daily_breakdown(conn, date_str=None):
    start, end = _day_bounds(date_str)
    rows = conn.execute(
        "SELECT domain, duration_s FROM activity_log WHERE ts>=? AND ts<?",
        (start, end)).fetchall()
    out = {"productive": 0.0, "distracting": 0.0, "neutral": 0.0, "total": 0.0}
    for r in rows:
        cat = _categorize(conn, r["domain"])
        out[cat] += r["duration_s"] or 0
        out["total"] += r["duration_s"] or 0
    return out


def calculate_score(conn, date_str=None):
    b = get_daily_breakdown(conn, date_str)
    if b["total"] <= 0:
        return 0.0
    return round(100.0 * b["productive"] / b["total"], 2)


def get_top_distractions(conn, days=7, limit=10):
    since = time.time() - days * 86400
    rows = conn.execute(
        "SELECT domain, SUM(duration_s) AS total FROM activity_log "
        "WHERE ts>=? AND domain IS NOT NULL AND domain != '' "
        "GROUP BY domain ORDER BY total DESC", (since,)).fetchall()
    out = []
    for r in rows:
        if _categorize(conn, r["domain"]) == "distracting":
            out.append({"domain": r["domain"], "seconds": r["total"] or 0})
            if len(out) >= limit:
                break
    return out


def range_summary(conn, days):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    totals = {"productive": 0.0, "distracting": 0.0, "neutral": 0.0, "total": 0.0}
    scores = []
    for i in range(days):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        b = get_daily_breakdown(conn, d)
        for k in totals:
            totals[k] += b[k]
        if b["total"] > 0:
            scores.append(100.0 * b["productive"] / b["total"])
    avg = round(sum(scores) / len(scores), 2) if scores else 0.0
    return {**totals, "avg_score": avg, "days": days}
