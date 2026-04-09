"""Decision log — log important decisions for later review."""
import time, json


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS decisions (
        id INTEGER PRIMARY KEY, title TEXT, context TEXT, options TEXT,
        choice TEXT, reasoning TEXT, outcome TEXT, outcome_rating INTEGER,
        made_at REAL, reviewed_at REAL
    )""")


def log_decision(conn, title: str, context: str, options: list,
                 choice: str, reasoning: str = "") -> int:
    _ensure_table(conn)
    cur = conn.execute(
        """INSERT INTO decisions (title, context, options, choice, reasoning, made_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (title, context, json.dumps(options), choice, reasoning, time.time()))
    conn.commit()
    return cur.lastrowid


def get_decision(conn, decision_id: int) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM decisions WHERE id=?", (decision_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    try:
        d["options"] = json.loads(d.get("options") or "[]")
    except Exception:
        d["options"] = []
    return d


def list_decisions(conn, limit: int = 50) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM decisions ORDER BY made_at DESC LIMIT ?", (limit,)).fetchall()
    return [{**dict(r), "options": json.loads(r["options"] or "[]")} for r in rows]


def update_outcome(conn, decision_id: int, outcome: str, rating: int):
    _ensure_table(conn)
    conn.execute(
        "UPDATE decisions SET outcome=?, outcome_rating=?, reviewed_at=? WHERE id=?",
        (outcome, rating, time.time(), decision_id))
    conn.commit()


def delete_decision(conn, decision_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM decisions WHERE id=?", (decision_id,))
    conn.commit()


def unreviewed_decisions(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM decisions WHERE outcome IS NULL OR outcome = '' ORDER BY made_at DESC"
    ).fetchall()
    return [{**dict(r), "options": json.loads(r["options"] or "[]")} for r in rows]


def search_decisions(conn, query: str) -> list:
    _ensure_table(conn)
    like = f"%{query}%"
    rows = conn.execute(
        """SELECT * FROM decisions WHERE title LIKE ? OR context LIKE ? OR reasoning LIKE ?
           ORDER BY made_at DESC""",
        (like, like, like)).fetchall()
    return [{**dict(r), "options": json.loads(r["options"] or "[]")} for r in rows]


def rating_stats(conn) -> dict:
    _ensure_table(conn)
    r = conn.execute(
        "SELECT AVG(outcome_rating) as avg, COUNT(outcome_rating) as n FROM decisions WHERE outcome_rating IS NOT NULL"
    ).fetchone()
    return {
        "count": r["n"] if r else 0,
        "avg_rating": round(r["avg"] or 0, 1),
    }
