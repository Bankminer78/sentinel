"""Scorecard system — track daily scores across multiple metrics."""
import time
from datetime import datetime, timedelta


DEFAULT_METRICS = [
    "productivity", "focus", "wellness", "happiness",
    "energy", "learning", "relationships", "finance",
]


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS scorecard_metrics (
        id INTEGER PRIMARY KEY, name TEXT UNIQUE, weight REAL DEFAULT 1.0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS scorecard_daily (
        id INTEGER PRIMARY KEY, date TEXT, metric TEXT, score INTEGER,
        UNIQUE(date, metric)
    )""")


def init_defaults(conn):
    _ensure_tables(conn)
    for m in DEFAULT_METRICS:
        conn.execute("INSERT OR IGNORE INTO scorecard_metrics (name) VALUES (?)", (m,))
    conn.commit()


def add_metric(conn, name: str, weight: float = 1.0) -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT OR IGNORE INTO scorecard_metrics (name, weight) VALUES (?, ?)",
        (name, weight))
    conn.commit()
    return cur.lastrowid or 0


def get_metrics(conn) -> list:
    _ensure_tables(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM scorecard_metrics ORDER BY name").fetchall()]


def record_score(conn, metric: str, score: int, date_str: str = None) -> int:
    """Score 1-10 for a metric on a day."""
    _ensure_tables(conn)
    d = date_str or datetime.now().strftime("%Y-%m-%d")
    conn.execute(
        "INSERT OR REPLACE INTO scorecard_daily (date, metric, score) VALUES (?, ?, ?)",
        (d, metric, score))
    conn.commit()
    r = conn.execute(
        "SELECT id FROM scorecard_daily WHERE date=? AND metric=?", (d, metric)).fetchone()
    return r["id"] if r else 0


def get_day_scores(conn, date_str: str = None) -> dict:
    _ensure_tables(conn)
    d = date_str or datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT metric, score FROM scorecard_daily WHERE date=?", (d,)).fetchall()
    return {r["metric"]: r["score"] for r in rows}


def overall_score(conn, date_str: str = None) -> float:
    scores = get_day_scores(conn, date_str)
    if not scores:
        return 0
    metrics = {m["name"]: m["weight"] for m in get_metrics(conn)}
    total = 0
    weight_sum = 0
    for metric, score in scores.items():
        weight = metrics.get(metric, 1.0)
        total += score * weight
        weight_sum += weight
    if weight_sum == 0:
        return 0
    # Scale 1-10 to 0-100
    return round(total / weight_sum * 10, 1)


def avg_metric(conn, metric: str, days: int = 30) -> float:
    _ensure_tables(conn)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    r = conn.execute(
        "SELECT AVG(score) as avg FROM scorecard_daily WHERE metric=? AND date >= ?",
        (metric, cutoff)).fetchone()
    return round(r["avg"] or 0, 1)


def week_overview(conn) -> list:
    today = datetime.now().date()
    result = []
    for i in range(7):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        result.append({
            "date": d,
            "score": overall_score(conn, d),
            "metrics": get_day_scores(conn, d),
        })
    return result


def delete_metric(conn, name: str):
    _ensure_tables(conn)
    conn.execute("DELETE FROM scorecard_metrics WHERE name=?", (name,))
    conn.execute("DELETE FROM scorecard_daily WHERE metric=?", (name,))
    conn.commit()


def trend(conn, metric: str, days: int = 14) -> str:
    _ensure_tables(conn)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT score FROM scorecard_daily WHERE metric=? AND date >= ? ORDER BY date",
        (metric, cutoff)).fetchall()
    if len(rows) < 4:
        return "stable"
    mid = len(rows) // 2
    first = sum(r["score"] for r in rows[:mid]) / mid
    second = sum(r["score"] for r in rows[mid:]) / (len(rows) - mid)
    if second > first + 1:
        return "improving"
    if second < first - 1:
        return "declining"
    return "stable"
