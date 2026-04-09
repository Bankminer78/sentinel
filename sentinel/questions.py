"""Questions — track questions you're asking yourself, with answers."""
import time


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY, question TEXT, category TEXT,
        answer TEXT, answered_at REAL, ts REAL
    )""")


def add_question(conn, question: str, category: str = "general") -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO questions (question, category, ts) VALUES (?, ?, ?)",
        (question, category, time.time()))
    conn.commit()
    return cur.lastrowid


def answer_question(conn, question_id: int, answer: str):
    _ensure_table(conn)
    conn.execute(
        "UPDATE questions SET answer=?, answered_at=? WHERE id=?",
        (answer, time.time(), question_id))
    conn.commit()


def get_questions(conn, answered: bool = None, category: str = None) -> list:
    _ensure_table(conn)
    q = "SELECT * FROM questions WHERE 1=1"
    params = []
    if answered is not None:
        if answered:
            q += " AND answer IS NOT NULL"
        else:
            q += " AND (answer IS NULL OR answer = '')"
    if category:
        q += " AND category=?"
        params.append(category)
    q += " ORDER BY ts DESC"
    rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def unanswered(conn) -> list:
    return get_questions(conn, answered=False)


def answered(conn) -> list:
    return get_questions(conn, answered=True)


def get_question(conn, question_id: int) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
    return dict(r) if r else None


def delete_question(conn, question_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM questions WHERE id=?", (question_id,))
    conn.commit()


def categories(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT DISTINCT category, COUNT(*) as count FROM questions GROUP BY category"
    ).fetchall()
    return [dict(r) for r in rows]


def search_questions(conn, query: str) -> list:
    _ensure_table(conn)
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM questions WHERE question LIKE ? OR answer LIKE ? ORDER BY ts DESC",
        (like, like)).fetchall()
    return [dict(r) for r in rows]


def oldest_unanswered(conn) -> dict:
    _ensure_table(conn)
    r = conn.execute(
        "SELECT * FROM questions WHERE answer IS NULL OR answer = '' ORDER BY ts ASC LIMIT 1"
    ).fetchone()
    return dict(r) if r else None
