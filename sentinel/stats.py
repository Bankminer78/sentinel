"""Stats & productivity module — scores, streaks, goals, summaries."""
import time
from datetime import datetime, timedelta

DISTRACTING = {"streaming", "social", "adult", "gaming", "shopping"}


def _day_bounds(date_str=None):
    d = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now().replace(
        hour=0, minute=0, second=0, microsecond=0)
    start = d.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    return start, start + 86400


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _categorize(conn, domain):
    if not domain:
        return "neutral"
    r = conn.execute("SELECT category FROM seen_domains WHERE domain=?", (domain,)).fetchone()
    cat = r["category"] if r else None
    if cat in DISTRACTING:
        return "distracting"
    return "productive"


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


def _range_summary(conn, days):
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


def get_week_summary(conn):
    return _range_summary(conn, 7)


def get_month_summary(conn):
    return _range_summary(conn, 30)


def productive_vs_distracted_hours(conn, date_str=None):
    b = get_daily_breakdown(conn, date_str)
    return {
        "productive_hours": round(b["productive"] / 3600, 2),
        "distracted_hours": round(b["distracting"] / 3600, 2),
    }


# --- Goals ---
def add_goal(conn, name, target_type, target_value, category=None):
    cur = conn.execute(
        "INSERT INTO goals (name,target_type,target_value,category,created_at) VALUES (?,?,?,?,?)",
        (name, target_type, target_value, category, time.time()))
    conn.commit()
    return cur.lastrowid


def get_goals(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM goals ORDER BY id").fetchall()]


def delete_goal(conn, goal_id):
    conn.execute("DELETE FROM goals WHERE id=?", (goal_id,))
    conn.commit()


def _goal_value(conn, goal, date_str):
    start, end = _day_bounds(date_str)
    cat = goal["category"]
    tt = goal["target_type"]
    if tt == "max_visits":
        if cat:
            n = conn.execute(
                "SELECT COUNT(*) AS n FROM activity_log al LEFT JOIN seen_domains s "
                "ON al.domain=s.domain WHERE al.ts>=? AND al.ts<? AND s.category=?",
                (start, end, cat)).fetchone()["n"]
        else:
            n = conn.execute(
                "SELECT COUNT(*) AS n FROM activity_log WHERE ts>=? AND ts<?",
                (start, end)).fetchone()["n"]
        return n
    # seconds-based
    if cat:
        rows = conn.execute(
            "SELECT al.duration_s, al.domain FROM activity_log al "
            "WHERE al.ts>=? AND al.ts<?", (start, end)).fetchall()
        total = 0.0
        for r in rows:
            c = _categorize(conn, r["domain"])
            if cat in DISTRACTING and c == "distracting":
                total += r["duration_s"] or 0
            elif cat == "productive" and c == "productive":
                total += r["duration_s"] or 0
            else:
                # exact category lookup
                rr = conn.execute("SELECT category FROM seen_domains WHERE domain=?",
                                  (r["domain"],)).fetchone()
                if rr and rr["category"] == cat:
                    total += r["duration_s"] or 0
        return total
    b = get_daily_breakdown(conn, date_str)
    return b["total"]


def check_goal_progress(conn, goal_id, date_str=None):
    g = conn.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
    if not g:
        return None
    g = dict(g)
    v = _goal_value(conn, g, date_str)
    tt, tv = g["target_type"], g["target_value"]
    if tt == "max_seconds":
        met = v <= tv
    elif tt == "min_seconds":
        met = v >= tv
    elif tt == "max_visits":
        met = v <= tv
    elif tt == "zero":
        met = v == 0
    else:
        met = False
    return {"goal_id": goal_id, "name": g["name"], "value": v,
            "target": tv, "target_type": tt, "met": met}


def evaluate_all_goals_today(conn):
    today = _today()
    return [check_goal_progress(conn, g["id"], today) for g in get_goals(conn)]


# --- Streaks ---
def update_streak(conn, goal_name, date_str, met):
    r = conn.execute("SELECT * FROM streaks WHERE goal_name=?", (goal_name,)).fetchone()
    if not r:
        cur, longest = (1, 1) if met else (0, 0)
        conn.execute(
            "INSERT INTO streaks (goal_name,current,longest,last_date) VALUES (?,?,?,?)",
            (goal_name, cur, longest, date_str))
    else:
        cur, longest = r["current"], r["longest"]
        if met:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
        conn.execute(
            "UPDATE streaks SET current=?, longest=?, last_date=? WHERE goal_name=?",
            (cur, longest, date_str, goal_name))
    conn.commit()


def get_streak(conn, goal_name):
    r = conn.execute("SELECT * FROM streaks WHERE goal_name=?", (goal_name,)).fetchone()
    if not r:
        return {"goal_name": goal_name, "current": 0, "longest": 0, "last_date": None}
    return dict(r)
