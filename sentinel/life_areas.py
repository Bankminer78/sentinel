"""Life areas — track balance across health, work, relationships, finance, etc."""
import time


DEFAULT_AREAS = [
    {"name": "Health", "icon": "💪", "description": "Physical and mental well-being"},
    {"name": "Work", "icon": "💼", "description": "Career and professional growth"},
    {"name": "Relationships", "icon": "❤️", "description": "Family, friends, romantic"},
    {"name": "Finance", "icon": "💰", "description": "Money and wealth"},
    {"name": "Learning", "icon": "📚", "description": "Skills and knowledge"},
    {"name": "Fun", "icon": "🎮", "description": "Hobbies and leisure"},
    {"name": "Family", "icon": "👨‍👩‍👧", "description": "Immediate family"},
    {"name": "Spiritual", "icon": "🧘", "description": "Meaning and purpose"},
]


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS life_areas (
        id INTEGER PRIMARY KEY, name TEXT UNIQUE, icon TEXT,
        description TEXT, current_score INTEGER DEFAULT 5, target_score INTEGER DEFAULT 10
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS life_area_log (
        id INTEGER PRIMARY KEY, area_id INTEGER, score INTEGER, note TEXT, ts REAL
    )""")


def init_default_areas(conn):
    _ensure_tables(conn)
    for a in DEFAULT_AREAS:
        conn.execute(
            "INSERT OR IGNORE INTO life_areas (name, icon, description) VALUES (?, ?, ?)",
            (a["name"], a["icon"], a["description"]))
    conn.commit()


def get_areas(conn) -> list:
    _ensure_tables(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM life_areas ORDER BY name").fetchall()]


def add_area(conn, name: str, icon: str = "", description: str = "") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT OR IGNORE INTO life_areas (name, icon, description) VALUES (?, ?, ?)",
        (name, icon, description))
    conn.commit()
    return cur.lastrowid


def delete_area(conn, area_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM life_areas WHERE id=?", (area_id,))
    conn.execute("DELETE FROM life_area_log WHERE area_id=?", (area_id,))
    conn.commit()


def update_score(conn, area_id: int, score: int, note: str = ""):
    _ensure_tables(conn)
    conn.execute("UPDATE life_areas SET current_score=? WHERE id=?", (score, area_id))
    conn.execute(
        "INSERT INTO life_area_log (area_id, score, note, ts) VALUES (?, ?, ?, ?)",
        (area_id, score, note, time.time()))
    conn.commit()


def set_target(conn, area_id: int, target: int):
    _ensure_tables(conn)
    conn.execute("UPDATE life_areas SET target_score=? WHERE id=?", (target, area_id))
    conn.commit()


def get_area_history(conn, area_id: int, days: int = 90) -> list:
    _ensure_tables(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT * FROM life_area_log WHERE area_id=? AND ts > ? ORDER BY ts DESC",
        (area_id, cutoff)).fetchall()
    return [dict(r) for r in rows]


def balance_score(conn) -> dict:
    """Overall life balance score — how close to target across all areas."""
    _ensure_tables(conn)
    areas = get_areas(conn)
    if not areas:
        return {"score": 0, "weakest": None, "strongest": None}
    total = 0
    for a in areas:
        ratio = min(1.0, a["current_score"] / max(1, a["target_score"]))
        total += ratio
    avg = (total / len(areas)) * 100
    weakest = min(areas, key=lambda a: a["current_score"])
    strongest = max(areas, key=lambda a: a["current_score"])
    return {
        "score": round(avg, 1),
        "weakest": weakest["name"],
        "strongest": strongest["name"],
        "areas_count": len(areas),
    }


def imbalance_alert(conn, threshold: int = 3) -> list:
    """Areas where current score is below threshold."""
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT * FROM life_areas WHERE current_score <= ?", (threshold,)).fetchall()
    return [dict(r) for r in rows]
