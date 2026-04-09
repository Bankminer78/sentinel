"""Weekly retrospectives — reflect on the week."""
import time, json
from datetime import datetime, timedelta
from . import classifier


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS retros (
        id INTEGER PRIMARY KEY, week_start TEXT, content TEXT,
        wins TEXT, challenges TEXT, next_week TEXT, created_at REAL
    )""")


def _current_week_start() -> str:
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    return monday.strftime("%Y-%m-%d")


def create_retro(conn, week_start: str = None, content: str = "",
                 wins: list = None, challenges: list = None, next_week: list = None) -> int:
    _ensure_table(conn)
    ws = week_start or _current_week_start()
    cur = conn.execute(
        "INSERT INTO retros (week_start, content, wins, challenges, next_week, created_at) VALUES (?,?,?,?,?,?)",
        (ws, content, json.dumps(wins or []), json.dumps(challenges or []),
         json.dumps(next_week or []), time.time()))
    conn.commit()
    return cur.lastrowid


def _row_to_retro(row) -> dict:
    d = dict(row)
    for key in ("wins", "challenges", "next_week"):
        try:
            d[key] = json.loads(d.get(key) or "[]")
        except Exception:
            d[key] = []
    return d


def get_retro(conn, week_start: str = None) -> dict:
    _ensure_table(conn)
    ws = week_start or _current_week_start()
    r = conn.execute("SELECT * FROM retros WHERE week_start=? ORDER BY id DESC LIMIT 1", (ws,)).fetchone()
    return _row_to_retro(r) if r else None


def get_retro_by_id(conn, retro_id: int) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM retros WHERE id=?", (retro_id,)).fetchone()
    return _row_to_retro(r) if r else None


def list_retros(conn, limit: int = 20) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM retros ORDER BY week_start DESC LIMIT ?", (limit,)).fetchall()
    return [_row_to_retro(r) for r in rows]


def delete_retro(conn, retro_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM retros WHERE id=?", (retro_id,))
    conn.commit()


async def generate_retro_template(conn, api_key: str) -> dict:
    from . import stats as stats_mod
    week = stats_mod.get_week_summary(conn)
    prompt = (f"Based on this week's data, suggest a retrospective template with 3 wins, 3 challenges, "
              f"and 3 focus areas for next week. Data: {json.dumps(week)}\n"
              f"Return JSON: {{\"wins\": [str], \"challenges\": [str], \"next_week\": [str]}}")
    try:
        result = await classifier.call_gemini(api_key, prompt, max_tokens=400)
        result = result.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(result)
    except Exception:
        return {"wins": [], "challenges": [], "next_week": []}
