"""Export data to CSV, Markdown, HTML."""
import csv, io, time
from datetime import datetime

from sentinel import db, stats as stats_mod


def _csv(rows, fieldnames) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames)
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in fieldnames})
    return buf.getvalue()


def rules_to_csv(conn) -> str:
    rules = db.get_rules(conn, active_only=False)
    rows = [{"id": r["id"], "text": r["text"], "action": r.get("action") or "block",
             "active": bool(r.get("active", 1))} for r in rules]
    return _csv(rows, ["id", "text", "action", "active"])


def rules_to_markdown(conn) -> str:
    rules = db.get_rules(conn, active_only=False)
    lines = ["# Sentinel Rules", "", f"_{len(rules)} rules_", ""]
    if not rules:
        lines.append("_No rules defined._")
        return "\n".join(lines)
    lines += ["| ID | Text | Action | Active |", "|----|------|--------|--------|"]
    for r in rules:
        active = "yes" if r.get("active", 1) else "no"
        text = (r["text"] or "").replace("|", "\\|")
        lines.append(f"| {r['id']} | {text} | {r.get('action') or 'block'} | {active} |")
    return "\n".join(lines) + "\n"


def stats_to_csv(conn, days: int = 30) -> str:
    rows = []
    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    for i in range(days):
        from datetime import timedelta
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        b = stats_mod.get_daily_breakdown(conn, d)
        rows.append({
            "date": d,
            "productive_s": round(b["productive"], 1),
            "distracting_s": round(b["distracting"], 1),
            "neutral_s": round(b["neutral"], 1),
            "total_s": round(b["total"], 1),
            "score": stats_mod.calculate_score(conn, d),
        })
    return _csv(rows, ["date", "productive_s", "distracting_s", "neutral_s", "total_s", "score"])


def activity_to_csv(conn, days: int = 7) -> str:
    since = time.time() - days * 86400
    acts = db.get_activities(conn, since=since, limit=10000)
    rows = [{
        "ts": a.get("ts"), "app": a.get("app") or "", "title": a.get("title") or "",
        "url": a.get("url") or "", "domain": a.get("domain") or "",
        "verdict": a.get("verdict") or "", "duration_s": a.get("duration_s") or 0,
    } for a in acts]
    return _csv(rows, ["ts", "app", "title", "url", "domain", "verdict", "duration_s"])


def full_report_markdown(conn) -> str:
    score = stats_mod.calculate_score(conn)
    week = stats_mod.get_week_summary(conn)
    top = stats_mod.get_top_distractions(conn, days=7)
    rules = db.get_rules(conn, active_only=False)
    lines = [
        "# Sentinel Report", "",
        f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_", "",
        "## Today", f"- Score: **{score}**", "",
        "## Last 7 Days",
        f"- Average score: {week.get('avg_score', 0)}",
        f"- Productive: {round(week.get('productive', 0) / 3600, 2)} h",
        f"- Distracting: {round(week.get('distracting', 0) / 3600, 2)} h", "",
        "## Top Distractions (7d)",
    ]
    if not top:
        lines.append("_None._")
    else:
        for t in top:
            lines.append(f"- {t['domain']}: {round(t['seconds'] / 60, 1)} min")
    lines += ["", "## Rules", f"_{len(rules)} total_"]
    return "\n".join(lines) + "\n"


def full_report_html(conn) -> str:
    md = full_report_markdown(conn)
    body = []
    for line in md.splitlines():
        if line.startswith("# "):
            body.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            body.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("- "):
            body.append(f"<li>{line[2:]}</li>")
        elif line.startswith("_") and line.endswith("_"):
            body.append(f"<p><em>{line[1:-1]}</em></p>")
        elif line.strip():
            body.append(f"<p>{line}</p>")
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Sentinel Report</title></head><body>"
            + "\n".join(body) + "</body></html>")
