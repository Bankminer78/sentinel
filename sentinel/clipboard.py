"""Clipboard monitoring — optional."""
import subprocess, time
from . import privacy


def get_clipboard() -> str:
    """Get current clipboard text via pbpaste."""
    try:
        r = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=3)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def set_clipboard(text: str) -> bool:
    try:
        subprocess.run(["pbcopy"], input=text, text=True, timeout=3, check=False)
        return True
    except Exception:
        return False


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS clipboard_history (
        id INTEGER PRIMARY KEY, content TEXT, length INTEGER, ts REAL
    )""")


def log_clipboard(conn, redact: bool = True) -> int:
    _ensure_table(conn)
    content = get_clipboard()
    if not content:
        return 0
    if redact:
        content = privacy.redact_pii(content)
    # Only store first 500 chars
    stored = content[:500]
    cur = conn.execute(
        "INSERT INTO clipboard_history (content, length, ts) VALUES (?, ?, ?)",
        (stored, len(content), time.time()))
    conn.commit()
    return cur.lastrowid


def get_history(conn, limit: int = 50) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM clipboard_history ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def search_history(conn, query: str) -> list:
    _ensure_table(conn)
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM clipboard_history WHERE content LIKE ? ORDER BY ts DESC",
        (like,)).fetchall()
    return [dict(r) for r in rows]


def clear_history(conn):
    _ensure_table(conn)
    conn.execute("DELETE FROM clipboard_history")
    conn.commit()


def purge_old(conn, days: int = 7) -> int:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    cur = conn.execute("DELETE FROM clipboard_history WHERE ts < ?", (cutoff,))
    conn.commit()
    return cur.rowcount or 0
