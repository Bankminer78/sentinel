"""Reflection journal — daily entries with mood and tags."""
import time
import json
import datetime as _dt
from . import db


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS journal (
        id INTEGER PRIMARY KEY, date TEXT, content TEXT, mood INTEGER,
        tags TEXT, created_at REAL
    )""")


def _today():
    return _dt.date.today().strftime("%Y-%m-%d")


def _row_to_dict(r):
    d = dict(r)
    d["tags"] = json.loads(d["tags"]) if d["tags"] else []
    return d


def add_entry(conn, content: str, mood: int = None, tags: list = None) -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO journal (date, content, mood, tags, created_at) VALUES (?, ?, ?, ?, ?)",
        (_today(), content, mood, json.dumps(tags or []), time.time()))
    conn.commit()
    return cur.lastrowid


def get_entries(conn, since: str = None, limit: int = 50) -> list:
    _ensure_table(conn)
    if since:
        rows = conn.execute(
            "SELECT * FROM journal WHERE date >= ? ORDER BY created_at DESC LIMIT ?",
            (since, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM journal ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_entry_by_id(conn, entry_id: int) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM journal WHERE id=?", (entry_id,)).fetchone()
    return _row_to_dict(r) if r else None


def delete_entry(conn, entry_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM journal WHERE id=?", (entry_id,))
    conn.commit()


def get_today_entry(conn) -> dict:
    _ensure_table(conn)
    r = conn.execute(
        "SELECT * FROM journal WHERE date=? ORDER BY created_at DESC LIMIT 1",
        (_today(),)).fetchone()
    return _row_to_dict(r) if r else None


def search_entries(conn, query: str) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM journal WHERE content LIKE ? ORDER BY created_at DESC",
        (f"%{query}%",)).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_mood_trend(conn, days: int = 30) -> list:
    _ensure_table(conn)
    cutoff = (_dt.date.today() - _dt.timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT date, AVG(mood) as avg_mood FROM journal "
        "WHERE date >= ? AND mood IS NOT NULL GROUP BY date ORDER BY date",
        (cutoff,)).fetchall()
    return [{"date": r["date"], "avg_mood": round(r["avg_mood"], 2)} for r in rows]
