"""Anomaly detection — spot unusual behavior patterns."""
from datetime import datetime
from collections import Counter


def _mean_std(values: list) -> tuple:
    if not values:
        return 0, 0
    m = sum(values) / len(values)
    var = sum((v - m) ** 2 for v in values) / len(values)
    return m, var ** 0.5


def is_anomaly(value: float, mean: float, std: float, threshold: float = 2.0) -> bool:
    """Z-score based anomaly detection."""
    if std == 0:
        return False
    return abs((value - mean) / std) > threshold


def detect_spending_anomalies(conn) -> list:
    """Find unusual spending patterns."""
    try:
        rows = conn.execute("SELECT amount, date FROM expenses").fetchall()
    except Exception:
        return []
    if not rows:
        return []
    amounts = [r["amount"] for r in rows]
    mean, std = _mean_std(amounts)
    anomalies = []
    for r in rows:
        if is_anomaly(r["amount"], mean, std):
            anomalies.append({"amount": r["amount"], "date": r["date"], "type": "spending"})
    return anomalies


def detect_activity_anomalies(conn, days: int = 30) -> list:
    """Find unusual activity patterns (e.g., visiting a new distracting site)."""
    import time
    cutoff = time.time() - days * 86400
    try:
        rows = conn.execute(
            "SELECT domain FROM activity_log WHERE ts > ?", (cutoff,)).fetchall()
    except Exception:
        return []
    domains = Counter(r["domain"] for r in rows if r["domain"])
    if not domains:
        return []
    values = list(domains.values())
    mean, std = _mean_std(values)
    anomalies = []
    for dom, count in domains.items():
        if is_anomaly(count, mean, std):
            anomalies.append({"domain": dom, "count": count, "type": "activity"})
    return anomalies


def detect_mood_anomalies(conn) -> list:
    """Find days with unusual mood."""
    try:
        rows = conn.execute("SELECT mood, ts FROM mood_log").fetchall()
    except Exception:
        return []
    if len(rows) < 5:
        return []
    moods = [r["mood"] for r in rows]
    mean, std = _mean_std(moods)
    anomalies = []
    for r in rows:
        if is_anomaly(r["mood"], mean, std):
            anomalies.append({"mood": r["mood"], "ts": r["ts"], "type": "mood"})
    return anomalies


def detect_all_anomalies(conn) -> dict:
    return {
        "spending": detect_spending_anomalies(conn),
        "activity": detect_activity_anomalies(conn),
        "mood": detect_mood_anomalies(conn),
    }


def z_score(value: float, mean: float, std: float) -> float:
    if std == 0:
        return 0
    return (value - mean) / std


def recent_unusual_days(conn, days: int = 7) -> list:
    """Days with unusually high distraction."""
    import time
    from datetime import datetime as dt
    cutoff = time.time() - 30 * 86400
    try:
        rows = conn.execute(
            "SELECT ts FROM activity_log WHERE verdict='block' AND ts > ?", (cutoff,)).fetchall()
    except Exception:
        return []
    by_day = Counter()
    for r in rows:
        day = dt.fromtimestamp(r["ts"]).strftime("%Y-%m-%d")
        by_day[day] += 1
    if not by_day:
        return []
    values = list(by_day.values())
    mean, std = _mean_std(values)
    unusual = []
    for day, count in by_day.items():
        if is_anomaly(count, mean, std):
            unusual.append({"date": day, "blocks": count})
    return unusual
