"""Telemetry — opt-in usage analytics (entirely local)."""
import time, json
from collections import Counter


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS telemetry_events (
        id INTEGER PRIMARY KEY, event TEXT, properties TEXT, ts REAL
    )""")


def is_enabled(conn) -> bool:
    from . import db as db_mod
    return db_mod.get_config(conn, "telemetry_enabled") == "1"


def enable(conn):
    from . import db as db_mod
    db_mod.set_config(conn, "telemetry_enabled", "1")


def disable(conn):
    from . import db as db_mod
    db_mod.set_config(conn, "telemetry_enabled", "0")


def track(conn, event: str, properties: dict = None):
    """Track a telemetry event (only if enabled)."""
    if not is_enabled(conn):
        return
    _ensure_table(conn)
    conn.execute(
        "INSERT INTO telemetry_events (event, properties, ts) VALUES (?, ?, ?)",
        (event, json.dumps(properties or {}), time.time()))
    conn.commit()


def get_events(conn, limit: int = 100) -> list:
    _ensure_table(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM telemetry_events ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()]


def event_counts(conn, days: int = 7) -> dict:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT event, COUNT(*) as c FROM telemetry_events WHERE ts > ? GROUP BY event",
        (cutoff,)).fetchall()
    return {r["event"]: r["c"] for r in rows}


def purge_old(conn, days: int = 30) -> int:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    cur = conn.execute("DELETE FROM telemetry_events WHERE ts < ?", (cutoff,))
    conn.commit()
    return cur.rowcount or 0


def summary(conn) -> dict:
    _ensure_table(conn)
    total = conn.execute("SELECT COUNT(*) as c FROM telemetry_events").fetchone()["c"]
    return {
        "enabled": is_enabled(conn),
        "total_events": total,
        "last_7_days": event_counts(conn, days=7),
    }
