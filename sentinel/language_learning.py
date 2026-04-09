"""Language learning tracker — flashcards, vocabulary, streaks."""
import time
from datetime import datetime, timedelta


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS languages (
        id INTEGER PRIMARY KEY, name TEXT UNIQUE, level TEXT DEFAULT 'beginner',
        started_at REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS vocabulary (
        id INTEGER PRIMARY KEY, language TEXT, word TEXT, translation TEXT,
        example TEXT, mastery INTEGER DEFAULT 0, added_at REAL,
        last_reviewed REAL DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS lang_sessions (
        id INTEGER PRIMARY KEY, language TEXT, minutes INTEGER,
        activity TEXT, ts REAL
    )""")


def add_language(conn, name: str, level: str = "beginner") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT OR IGNORE INTO languages (name, level, started_at) VALUES (?, ?, ?)",
        (name, level, time.time()))
    conn.commit()
    return cur.lastrowid or 0


def get_languages(conn) -> list:
    _ensure_tables(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM languages").fetchall()]


def add_word(conn, language: str, word: str, translation: str, example: str = "") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO vocabulary (language, word, translation, example, added_at) VALUES (?, ?, ?, ?, ?)",
        (language, word, translation, example, time.time()))
    conn.commit()
    return cur.lastrowid


def get_words(conn, language: str = None, limit: int = 100) -> list:
    _ensure_tables(conn)
    if language:
        rows = conn.execute(
            "SELECT * FROM vocabulary WHERE language=? ORDER BY added_at DESC LIMIT ?",
            (language, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM vocabulary ORDER BY added_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def review_word(conn, word_id: int, correct: bool):
    _ensure_tables(conn)
    r = conn.execute("SELECT mastery FROM vocabulary WHERE id=?", (word_id,)).fetchone()
    if not r:
        return
    new_mastery = r["mastery"] + (1 if correct else -1)
    new_mastery = max(0, min(5, new_mastery))
    conn.execute(
        "UPDATE vocabulary SET mastery=?, last_reviewed=? WHERE id=?",
        (new_mastery, time.time(), word_id))
    conn.commit()


def due_for_review(conn, language: str = None) -> list:
    """Spaced repetition — words due for review."""
    _ensure_tables(conn)
    intervals = {0: 0, 1: 86400, 2: 3 * 86400, 3: 7 * 86400, 4: 14 * 86400, 5: 30 * 86400}
    now = time.time()
    if language:
        rows = conn.execute("SELECT * FROM vocabulary WHERE language=?", (language,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM vocabulary").fetchall()
    due = []
    for r in rows:
        d = dict(r)
        interval = intervals.get(d["mastery"], 86400)
        if (d["last_reviewed"] + interval) <= now:
            due.append(d)
    return due


def log_session(conn, language: str, minutes: int, activity: str = "study") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO lang_sessions (language, minutes, activity, ts) VALUES (?, ?, ?, ?)",
        (language, minutes, activity, time.time()))
    conn.commit()
    return cur.lastrowid


def total_minutes(conn, language: str = None, days: int = 30) -> int:
    _ensure_tables(conn)
    cutoff = time.time() - days * 86400
    if language:
        r = conn.execute(
            "SELECT COALESCE(SUM(minutes), 0) as t FROM lang_sessions WHERE language=? AND ts > ?",
            (language, cutoff)).fetchone()
    else:
        r = conn.execute(
            "SELECT COALESCE(SUM(minutes), 0) as t FROM lang_sessions WHERE ts > ?",
            (cutoff,)).fetchone()
    return r["t"] or 0


def streak(conn, language: str) -> int:
    _ensure_tables(conn)
    current = datetime.now().date()
    days = 0
    while True:
        day_start = datetime.combine(current, datetime.min.time()).timestamp()
        day_end = day_start + 86400
        r = conn.execute(
            "SELECT COUNT(*) as c FROM lang_sessions WHERE language=? AND ts >= ? AND ts < ?",
            (language, day_start, day_end)).fetchone()
        if r["c"] > 0:
            days += 1
            current -= timedelta(days=1)
        else:
            if days == 0 and current == datetime.now().date():
                current -= timedelta(days=1)
                continue
            break
    return days


def vocabulary_count(conn, language: str = None) -> int:
    _ensure_tables(conn)
    if language:
        r = conn.execute(
            "SELECT COUNT(*) as c FROM vocabulary WHERE language=?", (language,)).fetchone()
    else:
        r = conn.execute("SELECT COUNT(*) as c FROM vocabulary").fetchone()
    return r["c"]


def mastery_stats(conn, language: str = None) -> dict:
    _ensure_tables(conn)
    if language:
        rows = conn.execute(
            "SELECT mastery, COUNT(*) as c FROM vocabulary WHERE language=? GROUP BY mastery",
            (language,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT mastery, COUNT(*) as c FROM vocabulary GROUP BY mastery").fetchall()
    return {r["mastery"]: r["c"] for r in rows}
