"""Reading tracker — books, pages, notes."""
import time
from datetime import datetime, timedelta


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY, title TEXT, author TEXT, total_pages INTEGER,
        current_page INTEGER DEFAULT 0, status TEXT DEFAULT 'reading',
        started_at REAL, finished_at REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS reading_sessions (
        id INTEGER PRIMARY KEY, book_id INTEGER, pages INTEGER, minutes INTEGER, ts REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS book_notes (
        id INTEGER PRIMARY KEY, book_id INTEGER, page INTEGER, note TEXT, ts REAL
    )""")


def add_book(conn, title: str, author: str = "", total_pages: int = 0) -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO books (title, author, total_pages, started_at, status) VALUES (?, ?, ?, ?, 'reading')",
        (title, author, total_pages, time.time()))
    conn.commit()
    return cur.lastrowid


def get_books(conn, status: str = None) -> list:
    _ensure_tables(conn)
    if status:
        rows = conn.execute("SELECT * FROM books WHERE status=?", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM books").fetchall()
    return [dict(r) for r in rows]


def get_book(conn, book_id: int) -> dict:
    _ensure_tables(conn)
    r = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
    return dict(r) if r else None


def log_reading(conn, book_id: int, pages: int, minutes: int) -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO reading_sessions (book_id, pages, minutes, ts) VALUES (?, ?, ?, ?)",
        (book_id, pages, minutes, time.time()))
    conn.execute("UPDATE books SET current_page = current_page + ? WHERE id=?",
                 (pages, book_id))
    conn.commit()
    return cur.lastrowid


def finish_book(conn, book_id: int):
    _ensure_tables(conn)
    conn.execute(
        "UPDATE books SET status='finished', finished_at=? WHERE id=?",
        (time.time(), book_id))
    conn.commit()


def add_note(conn, book_id: int, page: int, note: str) -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO book_notes (book_id, page, note, ts) VALUES (?, ?, ?, ?)",
        (book_id, page, note, time.time()))
    conn.commit()
    return cur.lastrowid


def get_notes(conn, book_id: int) -> list:
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT * FROM book_notes WHERE book_id=? ORDER BY page", (book_id,)).fetchall()
    return [dict(r) for r in rows]


def total_pages_read(conn, days: int = 7) -> int:
    _ensure_tables(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute(
        "SELECT COALESCE(SUM(pages), 0) as total FROM reading_sessions WHERE ts > ?",
        (cutoff,)).fetchone()
    return r["total"] or 0


def reading_streak(conn) -> int:
    _ensure_tables(conn)
    current = datetime.now().date()
    days = 0
    while True:
        day_start = datetime.combine(current, datetime.min.time()).timestamp()
        day_end = day_start + 86400
        r = conn.execute(
            "SELECT COUNT(*) as c FROM reading_sessions WHERE ts >= ? AND ts < ?",
            (day_start, day_end)).fetchone()
        if r["c"] > 0:
            days += 1
            current -= timedelta(days=1)
        else:
            if days == 0 and current == datetime.now().date():
                current -= timedelta(days=1)
                continue
            break
    return days


def books_finished_this_year(conn) -> int:
    _ensure_tables(conn)
    year_start = datetime(datetime.now().year, 1, 1).timestamp()
    r = conn.execute(
        "SELECT COUNT(*) as c FROM books WHERE status='finished' AND finished_at > ?",
        (year_start,)).fetchone()
    return r["c"]
