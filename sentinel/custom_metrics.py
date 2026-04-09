"""Custom metrics — user-defined metrics with logging and visualization."""
import time
from datetime import datetime


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS custom_metrics (
        id INTEGER PRIMARY KEY, name TEXT UNIQUE, unit TEXT,
        description TEXT, target REAL, created_at REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS custom_metric_log (
        id INTEGER PRIMARY KEY, metric_id INTEGER, value REAL, note TEXT, ts REAL
    )""")


def create_metric(conn, name: str, unit: str = "", description: str = "", target: float = None) -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT OR IGNORE INTO custom_metrics (name, unit, description, target, created_at) VALUES (?, ?, ?, ?, ?)",
        (name, unit, description, target, time.time()))
    conn.commit()
    return cur.lastrowid


def get_metrics(conn) -> list:
    _ensure_tables(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM custom_metrics ORDER BY name").fetchall()]


def get_metric(conn, metric_id: int) -> dict:
    _ensure_tables(conn)
    r = conn.execute("SELECT * FROM custom_metrics WHERE id=?", (metric_id,)).fetchone()
    return dict(r) if r else None


def delete_metric(conn, metric_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM custom_metrics WHERE id=?", (metric_id,))
    conn.execute("DELETE FROM custom_metric_log WHERE metric_id=?", (metric_id,))
    conn.commit()


def log_value(conn, metric_id: int, value: float, note: str = "") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO custom_metric_log (metric_id, value, note, ts) VALUES (?, ?, ?, ?)",
        (metric_id, value, note, time.time()))
    conn.commit()
    return cur.lastrowid


def get_values(conn, metric_id: int, days: int = 30) -> list:
    _ensure_tables(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT * FROM custom_metric_log WHERE metric_id=? AND ts > ? ORDER BY ts DESC",
        (metric_id, cutoff)).fetchall()
    return [dict(r) for r in rows]


def metric_stats(conn, metric_id: int, days: int = 30) -> dict:
    _ensure_tables(conn)
    values = [r["value"] for r in get_values(conn, metric_id, days)]
    if not values:
        return {"count": 0, "avg": 0, "min": 0, "max": 0, "latest": 0}
    return {
        "count": len(values),
        "avg": round(sum(values) / len(values), 2),
        "min": min(values),
        "max": max(values),
        "latest": values[0],
        "sum": sum(values),
    }


def metric_trend(conn, metric_id: int, days: int = 14) -> str:
    values = [r["value"] for r in get_values(conn, metric_id, days)]
    if len(values) < 4:
        return "stable"
    mid = len(values) // 2
    first = sum(values[:mid]) / mid
    second = sum(values[mid:]) / (len(values) - mid)
    if second > first * 1.1:
        return "improving"
    if second < first * 0.9:
        return "declining"
    return "stable"


def all_metrics_today(conn) -> list:
    """Latest value for each metric, today."""
    _ensure_tables(conn)
    today = datetime.now().strftime("%Y-%m-%d")
    today_ts = datetime.strptime(today, "%Y-%m-%d").timestamp()
    metrics = get_metrics(conn)
    result = []
    for m in metrics:
        r = conn.execute(
            "SELECT value, ts FROM custom_metric_log WHERE metric_id=? AND ts >= ? ORDER BY ts DESC LIMIT 1",
            (m["id"], today_ts)).fetchone()
        result.append({**m, "today_value": r["value"] if r else None})
    return result
