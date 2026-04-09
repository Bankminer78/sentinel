"""Whitelist mode — block everything except listed domains."""
from . import db


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS whitelist (
        domain TEXT PRIMARY KEY, added_at REAL
    )""")


def enable_whitelist_mode(conn):
    _ensure_table(conn)
    db.set_config(conn, "whitelist_mode", "1")


def disable_whitelist_mode(conn):
    db.set_config(conn, "whitelist_mode", "0")


def is_whitelist_mode(conn) -> bool:
    return db.get_config(conn, "whitelist_mode") == "1"


def add_to_whitelist(conn, domain: str):
    _ensure_table(conn)
    import time
    conn.execute("INSERT OR IGNORE INTO whitelist (domain, added_at) VALUES (?, ?)",
                 (domain.lower(), time.time()))
    conn.commit()


def remove_from_whitelist(conn, domain: str):
    _ensure_table(conn)
    conn.execute("DELETE FROM whitelist WHERE domain=?", (domain.lower(),))
    conn.commit()


def get_whitelist(conn) -> list:
    _ensure_table(conn)
    return [r["domain"] for r in conn.execute("SELECT domain FROM whitelist ORDER BY domain").fetchall()]


def is_whitelisted(conn, domain: str) -> bool:
    _ensure_table(conn)
    d = domain.lower()
    # Check exact match
    if conn.execute("SELECT 1 FROM whitelist WHERE domain=?", (d,)).fetchone():
        return True
    # Check parent domains
    parts = d.split(".")
    for i in range(1, len(parts) - 1):
        parent = ".".join(parts[i:])
        if conn.execute("SELECT 1 FROM whitelist WHERE domain=?", (parent,)).fetchone():
            return True
    return False
