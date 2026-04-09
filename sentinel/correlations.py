"""Find correlations in activity and productivity."""
import datetime as _dt
from collections import Counter
from . import stats, journal, habits


def _pearson(xs: list, ys: list) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs)
    dy = sum((y - my) ** 2 for y in ys)
    den = (dx * dy) ** 0.5
    if den == 0:
        return 0.0
    return round(num / den, 3)


def _daily_score_map(conn, days: int = 30) -> dict:
    today = _dt.date.today()
    out = {}
    for i in range(days):
        d = (today - _dt.timedelta(days=i)).strftime("%Y-%m-%d")
        b = stats.get_daily_breakdown(conn, d)
        if b["total"] > 0:
            out[d] = 100.0 * b["productive"] / b["total"]
    return out


def correlate_sleep_productivity(conn) -> float:
    trend = journal.get_mood_trend(conn, days=60)
    scores = _daily_score_map(conn, days=60)
    xs, ys = [], []
    for t in trend:
        if t["date"] in scores:
            xs.append(t["avg_mood"])
            ys.append(scores[t["date"]])
    return _pearson(xs, ys)


def correlate_habit_productivity(conn, habit_id: int) -> float:
    habits._ensure_table(conn)
    rows = conn.execute(
        "SELECT date FROM habit_log WHERE habit_id=?", (habit_id,)).fetchall()
    done = {r["date"] for r in rows}
    scores = _daily_score_map(conn, days=60)
    xs, ys = [], []
    for d, sc in scores.items():
        xs.append(1 if d in done else 0)
        ys.append(sc)
    return _pearson(xs, ys)


def correlate_time_of_day_productivity(conn) -> dict:
    rows = conn.execute(
        "SELECT ts, verdict FROM activity_log WHERE verdict IN ('allow','block')"
    ).fetchall()
    prod = Counter()
    total = Counter()
    for r in rows:
        h = _dt.datetime.fromtimestamp(r["ts"]).hour
        total[h] += 1
        if r["verdict"] == "allow":
            prod[h] += 1
    return {h: round(prod[h] / total[h], 3) if total[h] else 0.0 for h in total}


def correlate_domain_pairs(conn) -> list:
    rows = conn.execute(
        "SELECT ts, domain FROM activity_log WHERE domain IS NOT NULL ORDER BY ts"
    ).fetchall()
    pairs = Counter()
    prev, prev_ts = None, 0
    for r in rows:
        d = r["domain"]
        if prev and d != prev and (r["ts"] - prev_ts) < 600:
            pairs[tuple(sorted([prev, d]))] += 1
        prev, prev_ts = d, r["ts"]
    return [{"pair": list(k), "count": v} for k, v in pairs.most_common(10)]


def best_correlate_with_score(conn) -> dict:
    candidates = {"sleep_mood": correlate_sleep_productivity(conn)}
    for h in habits.get_habits(conn):
        candidates[f"habit_{h['id']}"] = correlate_habit_productivity(conn, h["id"])
    if not candidates:
        return {"name": None, "correlation": 0.0}
    name = max(candidates, key=lambda k: abs(candidates[k]))
    return {"name": name, "correlation": candidates[name]}
