"""Focus stones — gamified focus with virtual stones."""
import time, random
from datetime import datetime


STONE_TYPES = [
    {"id": "pebble", "name": "Pebble", "cost_minutes": 5, "color": "gray"},
    {"id": "river", "name": "River Stone", "cost_minutes": 15, "color": "blue"},
    {"id": "mountain", "name": "Mountain Stone", "cost_minutes": 30, "color": "brown"},
    {"id": "volcanic", "name": "Volcanic", "cost_minutes": 60, "color": "red"},
    {"id": "gem", "name": "Gem", "cost_minutes": 90, "color": "purple"},
    {"id": "crystal", "name": "Crystal", "cost_minutes": 120, "color": "cyan"},
    {"id": "diamond", "name": "Diamond", "cost_minutes": 180, "color": "white"},
]


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS focus_stones (
        id INTEGER PRIMARY KEY, stone_type TEXT, earned_at REAL, session_minutes INTEGER
    )""")


def earn_stone(conn, session_minutes: int) -> dict:
    """Earn a stone based on session length."""
    _ensure_table(conn)
    # Find the largest stone this session qualifies for
    eligible = [s for s in STONE_TYPES if s["cost_minutes"] <= session_minutes]
    if not eligible:
        return None
    stone = max(eligible, key=lambda s: s["cost_minutes"])
    conn.execute(
        "INSERT INTO focus_stones (stone_type, earned_at, session_minutes) VALUES (?, ?, ?)",
        (stone["id"], time.time(), session_minutes))
    conn.commit()
    return stone


def get_collection(conn) -> dict:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT stone_type, COUNT(*) as count FROM focus_stones GROUP BY stone_type"
    ).fetchall()
    collection = {r["stone_type"]: r["count"] for r in rows}
    return {
        s["id"]: {**s, "count": collection.get(s["id"], 0)}
        for s in STONE_TYPES
    }


def total_stones(conn) -> int:
    _ensure_table(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM focus_stones").fetchone()
    return r["c"] if r else 0


def total_value(conn) -> int:
    """Total minutes across all stones."""
    _ensure_table(conn)
    r = conn.execute("SELECT COALESCE(SUM(session_minutes), 0) as total FROM focus_stones").fetchone()
    return r["total"] or 0


def rarest_stone(conn) -> dict:
    _ensure_table(conn)
    collection = get_collection(conn)
    rarest = None
    for sid, data in collection.items():
        if data["count"] > 0:
            if rarest is None or STONE_TYPES[[s["id"] for s in STONE_TYPES].index(sid)]["cost_minutes"] > \
               STONE_TYPES[[s["id"] for s in STONE_TYPES].index(rarest)]["cost_minutes"]:
                rarest = sid
    return next((s for s in STONE_TYPES if s["id"] == rarest), None) if rarest else None


def list_stone_types() -> list:
    return list(STONE_TYPES)


def stone_info(stone_id: str) -> dict:
    return next((s for s in STONE_TYPES if s["id"] == stone_id), None)


def recent_stones(conn, limit: int = 10) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM focus_stones ORDER BY earned_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def stones_earned_today(conn) -> int:
    _ensure_table(conn)
    today_start = datetime.combine(datetime.now().date(), datetime.min.time()).timestamp()
    r = conn.execute(
        "SELECT COUNT(*) as c FROM focus_stones WHERE earned_at >= ?",
        (today_start,)).fetchone()
    return r["c"] if r else 0


def stones_this_week(conn) -> int:
    _ensure_table(conn)
    cutoff = time.time() - 7 * 86400
    r = conn.execute(
        "SELECT COUNT(*) as c FROM focus_stones WHERE earned_at > ?",
        (cutoff,)).fetchone()
    return r["c"] if r else 0
