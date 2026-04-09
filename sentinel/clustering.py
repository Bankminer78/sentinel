"""Simple clustering for activity patterns."""
from collections import Counter, defaultdict
from datetime import datetime


def k_means_1d(values: list, k: int = 3, iterations: int = 20) -> list:
    """Simple 1D k-means clustering."""
    if not values or k <= 0:
        return []
    values = sorted(values)
    # Initialize centroids evenly
    step = len(values) // k
    centroids = [values[i * step] for i in range(k)] if step > 0 else values[:k]
    if len(centroids) < k:
        return [list(values)]
    for _ in range(iterations):
        clusters = [[] for _ in range(k)]
        for v in values:
            # Find nearest centroid
            distances = [abs(v - c) for c in centroids]
            nearest = distances.index(min(distances))
            clusters[nearest].append(v)
        # Update centroids
        new_centroids = []
        for cluster in clusters:
            if cluster:
                new_centroids.append(sum(cluster) / len(cluster))
            else:
                new_centroids.append(centroids[len(new_centroids)])
        if new_centroids == centroids:
            break
        centroids = new_centroids
    return clusters


def cluster_by_hour(conn) -> dict:
    """Cluster activity by hour of day."""
    try:
        rows = conn.execute("SELECT ts FROM activity_log").fetchall()
    except Exception:
        return {}
    by_hour = Counter()
    for r in rows:
        h = datetime.fromtimestamp(r["ts"]).hour
        by_hour[h] += 1
    return dict(by_hour)


def cluster_by_domain(conn, limit: int = 10) -> list:
    """Group domains by visit count."""
    try:
        rows = conn.execute(
            "SELECT domain, COUNT(*) as c FROM activity_log WHERE domain != '' GROUP BY domain ORDER BY c DESC LIMIT ?",
            (limit,)).fetchall()
    except Exception:
        return []
    return [dict(r) for r in rows]


def identify_peak_times(conn) -> list:
    """Find peak activity times."""
    by_hour = cluster_by_hour(conn)
    if not by_hour:
        return []
    max_count = max(by_hour.values())
    return [h for h, c in by_hour.items() if c >= max_count * 0.7]


def group_activities_by_session(conn, gap_minutes: int = 15) -> list:
    """Group consecutive activities into sessions (gap-based clustering)."""
    try:
        rows = conn.execute(
            "SELECT ts, domain, app FROM activity_log ORDER BY ts"
        ).fetchall()
    except Exception:
        return []
    if not rows:
        return []
    sessions = []
    current = [dict(rows[0])]
    gap_s = gap_minutes * 60
    for r in rows[1:]:
        d = dict(r)
        if d["ts"] - current[-1]["ts"] > gap_s:
            sessions.append(current)
            current = [d]
        else:
            current.append(d)
    sessions.append(current)
    return sessions


def session_stats(sessions: list) -> dict:
    if not sessions:
        return {"count": 0, "avg_length": 0, "total_activities": 0}
    lengths = [len(s) for s in sessions]
    return {
        "count": len(sessions),
        "avg_length": round(sum(lengths) / len(lengths), 1),
        "total_activities": sum(lengths),
        "longest_session": max(lengths),
    }


def find_patterns(conn) -> dict:
    """Find common patterns in activity."""
    return {
        "by_hour": cluster_by_hour(conn),
        "top_domains": cluster_by_domain(conn),
        "peak_hours": identify_peak_times(conn),
    }
