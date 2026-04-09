"""Nutrition tracker — simple calorie and macro tracking."""
import time
from datetime import datetime, timedelta


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS meals (
        id INTEGER PRIMARY KEY, name TEXT, calories INTEGER,
        protein_g REAL, carbs_g REAL, fat_g REAL, meal_type TEXT, ts REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS nutrition_goals (
        id INTEGER PRIMARY KEY, calories INTEGER, protein_g INTEGER,
        carbs_g INTEGER, fat_g INTEGER
    )""")


def log_meal(conn, name: str, calories: int, protein_g: float = 0,
             carbs_g: float = 0, fat_g: float = 0, meal_type: str = "snack") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO meals (name, calories, protein_g, carbs_g, fat_g, meal_type, ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, calories, protein_g, carbs_g, fat_g, meal_type, time.time()))
    conn.commit()
    return cur.lastrowid


def get_meals(conn, days: int = 7) -> list:
    _ensure_tables(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT * FROM meals WHERE ts > ? ORDER BY ts DESC", (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def today_meals(conn) -> list:
    _ensure_tables(conn)
    today_start = datetime.combine(datetime.now().date(), datetime.min.time()).timestamp()
    rows = conn.execute(
        "SELECT * FROM meals WHERE ts >= ? ORDER BY ts", (today_start,)).fetchall()
    return [dict(r) for r in rows]


def today_totals(conn) -> dict:
    _ensure_tables(conn)
    today_start = datetime.combine(datetime.now().date(), datetime.min.time()).timestamp()
    r = conn.execute(
        """SELECT COALESCE(SUM(calories), 0) as cal,
                  COALESCE(SUM(protein_g), 0) as protein,
                  COALESCE(SUM(carbs_g), 0) as carbs,
                  COALESCE(SUM(fat_g), 0) as fat
           FROM meals WHERE ts >= ?""", (today_start,)).fetchone()
    return {
        "calories": r["cal"],
        "protein_g": round(r["protein"], 1),
        "carbs_g": round(r["carbs"], 1),
        "fat_g": round(r["fat"], 1),
    }


def set_goals(conn, calories: int, protein_g: int = 0, carbs_g: int = 0, fat_g: int = 0):
    _ensure_tables(conn)
    conn.execute("DELETE FROM nutrition_goals")
    conn.execute(
        "INSERT INTO nutrition_goals (calories, protein_g, carbs_g, fat_g) VALUES (?, ?, ?, ?)",
        (calories, protein_g, carbs_g, fat_g))
    conn.commit()


def get_goals(conn) -> dict:
    _ensure_tables(conn)
    r = conn.execute("SELECT * FROM nutrition_goals LIMIT 1").fetchone()
    return dict(r) if r else None


def goal_progress(conn) -> dict:
    goals = get_goals(conn)
    if not goals:
        return None
    totals = today_totals(conn)
    return {
        "calories": {"current": totals["calories"], "target": goals["calories"],
                     "percent": round(totals["calories"] / goals["calories"] * 100, 1) if goals["calories"] else 0},
        "protein": {"current": totals["protein_g"], "target": goals["protein_g"]},
        "carbs": {"current": totals["carbs_g"], "target": goals["carbs_g"]},
        "fat": {"current": totals["fat_g"], "target": goals["fat_g"]},
    }


def delete_meal(conn, meal_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM meals WHERE id=?", (meal_id,))
    conn.commit()


def weekly_avg_calories(conn) -> float:
    _ensure_tables(conn)
    cutoff = time.time() - 7 * 86400
    rows = conn.execute(
        "SELECT ts, calories FROM meals WHERE ts > ?", (cutoff,)).fetchall()
    by_day = {}
    for r in rows:
        day = datetime.fromtimestamp(r["ts"]).strftime("%Y-%m-%d")
        by_day[day] = by_day.get(day, 0) + r["calories"]
    if not by_day:
        return 0
    return round(sum(by_day.values()) / len(by_day), 1)
