"""URL shortener — internal short codes for sharing rules/content."""
import time, hashlib, base64


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS short_urls (
        code TEXT PRIMARY KEY, long_url TEXT, created_at REAL,
        click_count INTEGER DEFAULT 0
    )""")


def _generate_code(long_url: str, length: int = 6) -> str:
    h = hashlib.sha256(f"{long_url}:{time.time()}".encode()).digest()
    return base64.urlsafe_b64encode(h)[:length].decode().replace("=", "")


def shorten(conn, long_url: str) -> str:
    _ensure_table(conn)
    code = _generate_code(long_url)
    conn.execute(
        "INSERT INTO short_urls (code, long_url, created_at) VALUES (?, ?, ?)",
        (code, long_url, time.time()))
    conn.commit()
    return code


def expand(conn, code: str) -> str:
    _ensure_table(conn)
    r = conn.execute("SELECT long_url FROM short_urls WHERE code=?", (code,)).fetchone()
    if r:
        conn.execute("UPDATE short_urls SET click_count = click_count + 1 WHERE code=?", (code,))
        conn.commit()
        return r["long_url"]
    return None


def get_stats(conn, code: str) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM short_urls WHERE code=?", (code,)).fetchone()
    return dict(r) if r else None


def list_all(conn, limit: int = 100) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM short_urls ORDER BY click_count DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def delete(conn, code: str):
    _ensure_table(conn)
    conn.execute("DELETE FROM short_urls WHERE code=?", (code,))
    conn.commit()


def most_clicked(conn, limit: int = 10) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM short_urls ORDER BY click_count DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def total_count(conn) -> int:
    _ensure_table(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM short_urls").fetchone()
    return r["c"] if r else 0


def total_clicks(conn) -> int:
    _ensure_table(conn)
    r = conn.execute("SELECT COALESCE(SUM(click_count), 0) as total FROM short_urls").fetchone()
    return r["total"] or 0
