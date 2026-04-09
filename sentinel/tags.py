"""Tag system for rules."""
from . import db


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS rule_tags (
        rule_id INTEGER, tag TEXT, PRIMARY KEY (rule_id, tag)
    )""")


def add_tag(conn, rule_id: int, tag: str):
    _ensure_table(conn)
    tag = tag.strip().lower()
    if not tag:
        return
    conn.execute(
        "INSERT OR IGNORE INTO rule_tags (rule_id, tag) VALUES (?, ?)",
        (rule_id, tag))
    conn.commit()


def remove_tag(conn, rule_id: int, tag: str):
    _ensure_table(conn)
    conn.execute(
        "DELETE FROM rule_tags WHERE rule_id=? AND tag=?",
        (rule_id, tag.strip().lower()))
    conn.commit()


def get_tags(conn, rule_id: int) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT tag FROM rule_tags WHERE rule_id=? ORDER BY tag", (rule_id,)).fetchall()
    return [r["tag"] for r in rows]


def get_rules_by_tag(conn, tag: str) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT r.* FROM rules r JOIN rule_tags t ON r.id = t.rule_id "
        "WHERE t.tag = ? ORDER BY r.id", (tag.strip().lower(),)).fetchall()
    return [dict(r) for r in rows]


def list_all_tags(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT tag, COUNT(*) AS count FROM rule_tags GROUP BY tag ORDER BY count DESC, tag"
    ).fetchall()
    return [{"tag": r["tag"], "count": r["count"]} for r in rows]


def bulk_toggle_by_tag(conn, tag: str, active: bool) -> int:
    _ensure_table(conn)
    val = 1 if active else 0
    cur = conn.execute(
        "UPDATE rules SET active=? WHERE id IN "
        "(SELECT rule_id FROM rule_tags WHERE tag=?)",
        (val, tag.strip().lower()))
    conn.commit()
    return cur.rowcount
