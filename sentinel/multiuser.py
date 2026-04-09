"""Multi-user profiles — switch between user configurations."""
import time
from . import db


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, name TEXT UNIQUE, created_at REAL
    )""")


def create_user(conn, name: str) -> int:
    _ensure_table(conn)
    cur = conn.execute("INSERT OR IGNORE INTO users (name, created_at) VALUES (?, ?)",
                       (name, time.time()))
    if cur.lastrowid == 0:
        r = conn.execute("SELECT id FROM users WHERE name=?", (name,)).fetchone()
        conn.commit()
        return r["id"] if r else 0
    conn.commit()
    return cur.lastrowid


def list_users(conn) -> list:
    _ensure_table(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY name").fetchall()]


def switch_user(conn, user_id: int) -> bool:
    _ensure_table(conn)
    r = conn.execute("SELECT id, name FROM users WHERE id=?", (user_id,)).fetchone()
    if not r:
        return False
    db.set_config(conn, "current_user_id", str(user_id))
    db.set_config(conn, "current_user_name", r["name"])
    return True


def get_current_user(conn) -> dict:
    _ensure_table(conn)
    uid = db.get_config(conn, "current_user_id")
    if not uid:
        return {"id": None, "name": "default"}
    r = conn.execute("SELECT * FROM users WHERE id=?", (int(uid),)).fetchone()
    return dict(r) if r else {"id": None, "name": "default"}


def delete_user(conn, user_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    # If current user was deleted, clear
    if db.get_config(conn, "current_user_id") == str(user_id):
        db.set_config(conn, "current_user_id", "")
        db.set_config(conn, "current_user_name", "")
    conn.commit()


def user_stats(conn, user_id: int) -> dict:
    """Count activity etc. scoped to a user."""
    _ensure_table(conn)
    u = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not u:
        return {}
    return {"id": u["id"], "name": u["name"], "created_at": u["created_at"]}
