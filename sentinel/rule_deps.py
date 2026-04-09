"""Rule dependencies — cascade activation/deactivation."""
from . import db


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS rule_deps (
        id INTEGER PRIMARY KEY, parent_id INTEGER, child_id INTEGER,
        action TEXT DEFAULT 'activate'
    )""")


def add_dependency(conn, parent_id: int, child_id: int, action: str = "activate") -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO rule_deps (parent_id, child_id, action) VALUES (?, ?, ?)",
        (parent_id, child_id, action))
    conn.commit()
    return cur.lastrowid


def get_children(conn, parent_id: int) -> list:
    _ensure_table(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM rule_deps WHERE parent_id=?", (parent_id,)).fetchall()]


def get_parents(conn, child_id: int) -> list:
    _ensure_table(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM rule_deps WHERE child_id=?", (child_id,)).fetchall()]


def remove_dependency(conn, dep_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM rule_deps WHERE id=?", (dep_id,))
    conn.commit()


def list_all_deps(conn) -> list:
    _ensure_table(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM rule_deps").fetchall()]


def resolve_cascade(conn, rule_id: int, active: bool) -> list:
    """When a rule toggles, propagate to dependencies. Returns affected rule IDs."""
    _ensure_table(conn)
    affected = []
    children = get_children(conn, rule_id)
    for dep in children:
        target_id = dep["child_id"]
        should_activate = (dep["action"] == "activate" and active) or \
                          (dep["action"] == "deactivate" and not active)
        # Get current state
        r = conn.execute("SELECT active FROM rules WHERE id=?", (target_id,)).fetchone()
        if r is None:
            continue
        new_state = 1 if should_activate else 0
        if r["active"] != new_state:
            conn.execute("UPDATE rules SET active=? WHERE id=?", (new_state, target_id))
            affected.append(target_id)
    conn.commit()
    return affected
