"""Simple Kanban board — task management with columns."""
import time


DEFAULT_COLUMNS = ["backlog", "todo", "in_progress", "review", "done"]


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS kanban_boards (
        id INTEGER PRIMARY KEY, name TEXT UNIQUE, columns TEXT, created_at REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS kanban_cards (
        id INTEGER PRIMARY KEY, board_id INTEGER, title TEXT, description TEXT,
        column TEXT, position INTEGER, priority INTEGER DEFAULT 0,
        assignee TEXT, created_at REAL, completed_at REAL
    )""")


def create_board(conn, name: str, columns: list = None) -> int:
    _ensure_tables(conn)
    import json
    cols = columns or DEFAULT_COLUMNS
    cur = conn.execute(
        "INSERT OR IGNORE INTO kanban_boards (name, columns, created_at) VALUES (?, ?, ?)",
        (name, json.dumps(cols), time.time()))
    if cur.lastrowid == 0:
        r = conn.execute("SELECT id FROM kanban_boards WHERE name=?", (name,)).fetchone()
        conn.commit()
        return r["id"] if r else 0
    conn.commit()
    return cur.lastrowid


def get_boards(conn) -> list:
    _ensure_tables(conn)
    import json
    rows = conn.execute("SELECT * FROM kanban_boards").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["columns"] = json.loads(d.get("columns") or "[]")
        except Exception:
            d["columns"] = DEFAULT_COLUMNS
        result.append(d)
    return result


def add_card(conn, board_id: int, title: str, column: str = "backlog",
             description: str = "", priority: int = 0, assignee: str = "") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        """INSERT INTO kanban_cards (board_id, title, description, column, position, priority, assignee, created_at)
           VALUES (?, ?, ?, ?, 0, ?, ?, ?)""",
        (board_id, title, description, column, priority, assignee, time.time()))
    conn.commit()
    return cur.lastrowid


def get_cards(conn, board_id: int, column: str = None) -> list:
    _ensure_tables(conn)
    q = "SELECT * FROM kanban_cards WHERE board_id=?"
    params = [board_id]
    if column:
        q += " AND column=?"
        params.append(column)
    q += " ORDER BY priority DESC, position ASC"
    rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def move_card(conn, card_id: int, column: str):
    _ensure_tables(conn)
    completed_at = time.time() if column == "done" else None
    conn.execute(
        "UPDATE kanban_cards SET column=?, completed_at=? WHERE id=?",
        (column, completed_at, card_id))
    conn.commit()


def delete_card(conn, card_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM kanban_cards WHERE id=?", (card_id,))
    conn.commit()


def update_card(conn, card_id: int, title: str = None, description: str = None,
                priority: int = None):
    _ensure_tables(conn)
    updates = []
    params = []
    if title is not None:
        updates.append("title=?")
        params.append(title)
    if description is not None:
        updates.append("description=?")
        params.append(description)
    if priority is not None:
        updates.append("priority=?")
        params.append(priority)
    if updates:
        params.append(card_id)
        conn.execute(f"UPDATE kanban_cards SET {','.join(updates)} WHERE id=?", params)
        conn.commit()


def board_summary(conn, board_id: int) -> dict:
    _ensure_tables(conn)
    cards = get_cards(conn, board_id)
    by_column = {}
    for c in cards:
        by_column.setdefault(c["column"], []).append(c)
    return {
        "total": len(cards),
        "by_column": {k: len(v) for k, v in by_column.items()},
        "completed": sum(1 for c in cards if c["column"] == "done"),
        "in_progress": sum(1 for c in cards if c["column"] == "in_progress"),
    }


def delete_board(conn, board_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM kanban_boards WHERE id=?", (board_id,))
    conn.execute("DELETE FROM kanban_cards WHERE board_id=?", (board_id,))
    conn.commit()
