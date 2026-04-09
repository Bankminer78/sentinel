"""AI chat history — persistent conversation memory with the AI coach."""
import time, json


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS chat_sessions (
        id INTEGER PRIMARY KEY, title TEXT, created_at REAL, updated_at REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY, session_id INTEGER, role TEXT, content TEXT, ts REAL
    )""")


def create_session(conn, title: str = "New chat") -> int:
    _ensure_tables(conn)
    now = time.time()
    cur = conn.execute(
        "INSERT INTO chat_sessions (title, created_at, updated_at) VALUES (?, ?, ?)",
        (title, now, now))
    conn.commit()
    return cur.lastrowid


def add_message(conn, session_id: int, role: str, content: str) -> int:
    _ensure_tables(conn)
    now = time.time()
    cur = conn.execute(
        "INSERT INTO chat_messages (session_id, role, content, ts) VALUES (?, ?, ?, ?)",
        (session_id, role, content, now))
    conn.execute("UPDATE chat_sessions SET updated_at=? WHERE id=?", (now, session_id))
    conn.commit()
    return cur.lastrowid


def get_session(conn, session_id: int) -> dict:
    _ensure_tables(conn)
    s = conn.execute("SELECT * FROM chat_sessions WHERE id=?", (session_id,)).fetchone()
    if not s:
        return None
    d = dict(s)
    d["messages"] = [dict(m) for m in conn.execute(
        "SELECT * FROM chat_messages WHERE session_id=? ORDER BY ts ASC",
        (session_id,)).fetchall()]
    return d


def list_sessions(conn, limit: int = 50) -> list:
    _ensure_tables(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM chat_sessions ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()]


def delete_session(conn, session_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM chat_sessions WHERE id=?", (session_id,))
    conn.execute("DELETE FROM chat_messages WHERE session_id=?", (session_id,))
    conn.commit()


def get_messages(conn, session_id: int) -> list:
    _ensure_tables(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM chat_messages WHERE session_id=? ORDER BY ts ASC",
        (session_id,)).fetchall()]


def rename_session(conn, session_id: int, title: str):
    _ensure_tables(conn)
    conn.execute("UPDATE chat_sessions SET title=? WHERE id=?", (title, session_id))
    conn.commit()


def search_history(conn, query: str) -> list:
    _ensure_tables(conn)
    like = f"%{query}%"
    return [dict(r) for r in conn.execute(
        "SELECT * FROM chat_messages WHERE content LIKE ? ORDER BY ts DESC",
        (like,)).fetchall()]


def get_session_context(conn, session_id: int, max_messages: int = 10) -> list:
    """Recent messages formatted for LLM context."""
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT role, content FROM chat_messages WHERE session_id=? ORDER BY ts DESC LIMIT ?",
        (session_id, max_messages)).fetchall()
    return list(reversed([{"role": r["role"], "content": r["content"]} for r in rows]))
