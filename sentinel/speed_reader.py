"""Speed reader — RSVP-style speed reading trainer."""
import time


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS speed_reading_sessions (
        id INTEGER PRIMARY KEY, wpm INTEGER, words_read INTEGER,
        duration_s REAL, comprehension INTEGER, ts REAL
    )""")


def log_session(conn, wpm: int, words_read: int, duration_s: float,
                comprehension: int = None) -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        """INSERT INTO speed_reading_sessions (wpm, words_read, duration_s, comprehension, ts)
           VALUES (?, ?, ?, ?, ?)""",
        (wpm, words_read, duration_s, comprehension, time.time()))
    conn.commit()
    return cur.lastrowid


def get_sessions(conn, days: int = 30) -> list:
    _ensure_tables(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT * FROM speed_reading_sessions WHERE ts > ? ORDER BY ts DESC", (cutoff,)
    ).fetchall()
    return [dict(r) for r in rows]


def best_wpm(conn) -> int:
    _ensure_tables(conn)
    r = conn.execute("SELECT MAX(wpm) as max FROM speed_reading_sessions").fetchone()
    return r["max"] or 0


def avg_wpm(conn, days: int = 30) -> float:
    _ensure_tables(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute(
        "SELECT AVG(wpm) as avg FROM speed_reading_sessions WHERE ts > ?",
        (cutoff,)).fetchone()
    return round(r["avg"] or 0, 1)


def total_words_read(conn, days: int = 30) -> int:
    _ensure_tables(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute(
        "SELECT COALESCE(SUM(words_read), 0) as total FROM speed_reading_sessions WHERE ts > ?",
        (cutoff,)).fetchone()
    return r["total"] or 0


def avg_comprehension(conn, days: int = 30) -> float:
    _ensure_tables(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute(
        "SELECT AVG(comprehension) as avg FROM speed_reading_sessions WHERE ts > ? AND comprehension IS NOT NULL",
        (cutoff,)).fetchone()
    return round(r["avg"] or 0, 1)


def get_recommended_wpm(conn) -> int:
    """Suggest next target WPM based on progress."""
    avg = avg_wpm(conn, days=14)
    if avg == 0:
        return 250
    # Add 25 WPM as next target
    return int(avg + 25)


def rsvp_split(text: str, chunk_size: int = 1) -> list:
    """Split text into chunks for RSVP-style display."""
    words = text.split()
    if chunk_size <= 1:
        return words
    return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]


def delay_for_wpm(wpm: int) -> float:
    """Seconds per word at a given WPM."""
    if wpm <= 0:
        return 0.24  # 250 WPM default
    return 60.0 / wpm


def estimate_finish_time(word_count: int, wpm: int) -> float:
    """Estimated seconds to finish a text at a WPM."""
    if wpm <= 0:
        return 0
    return word_count * 60.0 / wpm


def delete_session(conn, session_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM speed_reading_sessions WHERE id=?", (session_id,))
    conn.commit()


def total_sessions(conn) -> int:
    _ensure_tables(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM speed_reading_sessions").fetchone()
    return r["c"] if r else 0
