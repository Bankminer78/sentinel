"""Weight tracker — log weight, BMI, trends."""
import time
from datetime import datetime, timedelta


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS weight_log (
        id INTEGER PRIMARY KEY, weight_kg REAL, notes TEXT, date TEXT UNIQUE, ts REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS weight_config (
        id INTEGER PRIMARY KEY, height_cm REAL, target_kg REAL
    )""")


def log_weight(conn, weight_kg: float, notes: str = "") -> int:
    _ensure_tables(conn)
    date_str = datetime.now().strftime("%Y-%m-%d")
    cur = conn.execute(
        "INSERT OR REPLACE INTO weight_log (weight_kg, notes, date, ts) VALUES (?, ?, ?, ?)",
        (weight_kg, notes, date_str, time.time()))
    conn.commit()
    return cur.lastrowid


def get_weights(conn, days: int = 30) -> list:
    _ensure_tables(conn)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM weight_log WHERE date >= ? ORDER BY date DESC", (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def current_weight(conn) -> float:
    _ensure_tables(conn)
    r = conn.execute("SELECT weight_kg FROM weight_log ORDER BY date DESC LIMIT 1").fetchone()
    return r["weight_kg"] if r else 0


def set_height(conn, height_cm: float):
    _ensure_tables(conn)
    conn.execute("DELETE FROM weight_config")
    conn.execute("INSERT INTO weight_config (height_cm) VALUES (?)", (height_cm,))
    conn.commit()


def set_target(conn, target_kg: float):
    _ensure_tables(conn)
    r = conn.execute("SELECT * FROM weight_config LIMIT 1").fetchone()
    if r:
        conn.execute("UPDATE weight_config SET target_kg=?", (target_kg,))
    else:
        conn.execute("INSERT INTO weight_config (target_kg) VALUES (?)", (target_kg,))
    conn.commit()


def get_config(conn) -> dict:
    _ensure_tables(conn)
    r = conn.execute("SELECT * FROM weight_config LIMIT 1").fetchone()
    return dict(r) if r else {"height_cm": 0, "target_kg": 0}


def bmi(conn) -> float:
    cfg = get_config(conn)
    weight = current_weight(conn)
    if not cfg.get("height_cm") or not weight:
        return 0
    h_m = cfg["height_cm"] / 100
    return round(weight / (h_m * h_m), 1)


def trend(conn, days: int = 30) -> str:
    weights = get_weights(conn, days)
    if len(weights) < 2:
        return "stable"
    first = weights[-1]["weight_kg"]
    last = weights[0]["weight_kg"]
    diff = last - first
    if diff > 1:
        return "gaining"
    if diff < -1:
        return "losing"
    return "stable"


def progress_to_target(conn) -> dict:
    cfg = get_config(conn)
    target = cfg.get("target_kg", 0)
    current = current_weight(conn)
    if not target or not current:
        return {"target": 0, "current": 0, "diff": 0}
    return {
        "target": target,
        "current": current,
        "diff": round(current - target, 1),
        "reached": abs(current - target) < 0.5,
    }


def avg_weekly(conn) -> float:
    weights = get_weights(conn, days=7)
    if not weights:
        return 0
    return round(sum(w["weight_kg"] for w in weights) / len(weights), 1)


def delete_entry(conn, date_str: str):
    _ensure_tables(conn)
    conn.execute("DELETE FROM weight_log WHERE date=?", (date_str,))
    conn.commit()
