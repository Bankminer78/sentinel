"""Social feed — share wins and support team members."""
import time


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS feed_posts (
        id INTEGER PRIMARY KEY, author TEXT, content TEXT,
        post_type TEXT DEFAULT 'general', ts REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS feed_reactions (
        id INTEGER PRIMARY KEY, post_id INTEGER, author TEXT,
        reaction TEXT, ts REAL
    )""")


def create_post(conn, author: str, content: str, post_type: str = "general") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO feed_posts (author, content, post_type, ts) VALUES (?, ?, ?, ?)",
        (author, content, post_type, time.time()))
    conn.commit()
    return cur.lastrowid


def get_feed(conn, limit: int = 20) -> list:
    _ensure_tables(conn)
    posts = [dict(r) for r in conn.execute(
        "SELECT * FROM feed_posts ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()]
    # Attach reactions
    for p in posts:
        reactions = conn.execute(
            "SELECT reaction, COUNT(*) as c FROM feed_reactions WHERE post_id=? GROUP BY reaction",
            (p["id"],)).fetchall()
        p["reactions"] = {r["reaction"]: r["c"] for r in reactions}
    return posts


def get_post(conn, post_id: int) -> dict:
    _ensure_tables(conn)
    r = conn.execute("SELECT * FROM feed_posts WHERE id=?", (post_id,)).fetchone()
    return dict(r) if r else None


def delete_post(conn, post_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM feed_posts WHERE id=?", (post_id,))
    conn.execute("DELETE FROM feed_reactions WHERE post_id=?", (post_id,))
    conn.commit()


def react(conn, post_id: int, author: str, reaction: str) -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO feed_reactions (post_id, author, reaction, ts) VALUES (?, ?, ?, ?)",
        (post_id, author, reaction, time.time()))
    conn.commit()
    return cur.lastrowid


def get_reactions(conn, post_id: int) -> list:
    _ensure_tables(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM feed_reactions WHERE post_id=?", (post_id,)).fetchall()]


def remove_reaction(conn, reaction_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM feed_reactions WHERE id=?", (reaction_id,))
    conn.commit()


def filter_by_type(conn, post_type: str, limit: int = 20) -> list:
    _ensure_tables(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM feed_posts WHERE post_type=? ORDER BY ts DESC LIMIT ?",
        (post_type, limit)).fetchall()]


def filter_by_author(conn, author: str, limit: int = 20) -> list:
    _ensure_tables(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM feed_posts WHERE author=? ORDER BY ts DESC LIMIT ?",
        (author, limit)).fetchall()]


def share_win(conn, author: str, content: str) -> int:
    return create_post(conn, author, content, "win")


def share_goal(conn, author: str, goal_text: str) -> int:
    return create_post(conn, author, goal_text, "goal")
