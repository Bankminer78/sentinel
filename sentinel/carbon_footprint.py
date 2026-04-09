"""Carbon footprint tracker — log activities that impact carbon footprint."""
import time
from datetime import datetime, timedelta


# Estimated kg CO2 per unit
EMISSION_FACTORS = {
    "flight_short": 0.15,  # kg CO2 per km
    "flight_long": 0.11,
    "car_km": 0.18,
    "train_km": 0.04,
    "bus_km": 0.07,
    "beef_meal": 7.0,  # kg CO2 per meal
    "chicken_meal": 2.5,
    "vegetarian_meal": 1.5,
    "vegan_meal": 0.9,
    "electricity_kwh": 0.4,
    "gas_therm": 5.3,
    "clothing_item": 15.0,
    "laptop_hour": 0.02,
}


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS carbon_log (
        id INTEGER PRIMARY KEY, activity TEXT, units REAL,
        kg_co2 REAL, note TEXT, date TEXT, ts REAL
    )""")


def log_activity(conn, activity: str, units: float, note: str = "") -> int:
    _ensure_table(conn)
    factor = EMISSION_FACTORS.get(activity, 0)
    kg = factor * units
    date_str = datetime.now().strftime("%Y-%m-%d")
    cur = conn.execute(
        "INSERT INTO carbon_log (activity, units, kg_co2, note, date, ts) VALUES (?, ?, ?, ?, ?, ?)",
        (activity, units, kg, note, date_str, time.time()))
    conn.commit()
    return cur.lastrowid


def get_log(conn, days: int = 30) -> list:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT * FROM carbon_log WHERE ts > ? ORDER BY ts DESC", (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def total_kg(conn, days: int = 30) -> float:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute(
        "SELECT COALESCE(SUM(kg_co2), 0) as total FROM carbon_log WHERE ts > ?",
        (cutoff,)).fetchone()
    return round(r["total"] or 0, 2)


def by_activity(conn, days: int = 30) -> dict:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT activity, SUM(kg_co2) as total FROM carbon_log WHERE ts > ? GROUP BY activity",
        (cutoff,)).fetchall()
    return {r["activity"]: round(r["total"], 2) for r in rows}


def list_activities() -> list:
    return list(EMISSION_FACTORS.keys())


def get_factor(activity: str) -> float:
    return EMISSION_FACTORS.get(activity, 0)


def daily_average(conn, days: int = 30) -> float:
    total = total_kg(conn, days)
    return round(total / days, 2) if days > 0 else 0


def delete_log_entry(conn, entry_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM carbon_log WHERE id=?", (entry_id,))
    conn.commit()


def biggest_sources(conn, days: int = 30, limit: int = 5) -> list:
    by_act = by_activity(conn, days)
    sorted_items = sorted(by_act.items(), key=lambda x: x[1], reverse=True)
    return [{"activity": k, "kg_co2": v} for k, v in sorted_items[:limit]]


def set_target(conn, monthly_kg: float):
    from . import db as db_mod
    db_mod.set_config(conn, "carbon_monthly_target", str(monthly_kg))


def get_target(conn) -> float:
    from . import db as db_mod
    target = db_mod.get_config(conn, "carbon_monthly_target")
    return float(target) if target else 0
