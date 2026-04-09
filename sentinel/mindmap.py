"""Mindmap — hierarchical note structure for planning."""
import time, json


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS mindmaps (
        id INTEGER PRIMARY KEY, title TEXT, root_node_id INTEGER, created_at REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS mindmap_nodes (
        id INTEGER PRIMARY KEY, mindmap_id INTEGER, parent_id INTEGER,
        content TEXT, position INTEGER DEFAULT 0, created_at REAL
    )""")


def create_mindmap(conn, title: str) -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO mindmaps (title, created_at) VALUES (?, ?)",
        (title, time.time()))
    mindmap_id = cur.lastrowid
    root_cur = conn.execute(
        "INSERT INTO mindmap_nodes (mindmap_id, content, created_at) VALUES (?, ?, ?)",
        (mindmap_id, title, time.time()))
    root_id = root_cur.lastrowid
    conn.execute("UPDATE mindmaps SET root_node_id=? WHERE id=?", (root_id, mindmap_id))
    conn.commit()
    return mindmap_id


def add_node(conn, mindmap_id: int, parent_id: int, content: str) -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO mindmap_nodes (mindmap_id, parent_id, content, created_at) VALUES (?, ?, ?, ?)",
        (mindmap_id, parent_id, content, time.time()))
    conn.commit()
    return cur.lastrowid


def get_mindmap(conn, mindmap_id: int) -> dict:
    _ensure_tables(conn)
    r = conn.execute("SELECT * FROM mindmaps WHERE id=?", (mindmap_id,)).fetchone()
    if not r:
        return None
    nodes = [dict(n) for n in conn.execute(
        "SELECT * FROM mindmap_nodes WHERE mindmap_id=?", (mindmap_id,)).fetchall()]
    return {**dict(r), "nodes": nodes}


def get_children(conn, parent_id: int) -> list:
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT * FROM mindmap_nodes WHERE parent_id=? ORDER BY position", (parent_id,)).fetchall()
    return [dict(r) for r in rows]


def delete_node(conn, node_id: int):
    _ensure_tables(conn)
    # Recursively delete children
    children = get_children(conn, node_id)
    for c in children:
        delete_node(conn, c["id"])
    conn.execute("DELETE FROM mindmap_nodes WHERE id=?", (node_id,))
    conn.commit()


def delete_mindmap(conn, mindmap_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM mindmaps WHERE id=?", (mindmap_id,))
    conn.execute("DELETE FROM mindmap_nodes WHERE mindmap_id=?", (mindmap_id,))
    conn.commit()


def list_mindmaps(conn) -> list:
    _ensure_tables(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM mindmaps").fetchall()]


def update_node(conn, node_id: int, content: str):
    _ensure_tables(conn)
    conn.execute("UPDATE mindmap_nodes SET content=? WHERE id=?", (content, node_id))
    conn.commit()


def render_ascii(conn, mindmap_id: int) -> str:
    """Render a mindmap as indented ASCII."""
    mm = get_mindmap(conn, mindmap_id)
    if not mm:
        return ""
    lines = []

    def traverse(node_id: int, depth: int):
        node = next((n for n in mm["nodes"] if n["id"] == node_id), None)
        if node:
            lines.append("  " * depth + "- " + node["content"])
            children = [n for n in mm["nodes"] if n["parent_id"] == node_id]
            for c in sorted(children, key=lambda x: x.get("position", 0)):
                traverse(c["id"], depth + 1)

    if mm["root_node_id"]:
        traverse(mm["root_node_id"], 0)
    return "\n".join(lines)


def count_nodes(conn, mindmap_id: int) -> int:
    _ensure_tables(conn)
    r = conn.execute(
        "SELECT COUNT(*) as c FROM mindmap_nodes WHERE mindmap_id=?",
        (mindmap_id,)).fetchone()
    return r["c"] if r else 0
