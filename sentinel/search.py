"""Global full-text search across all Sentinel data."""


def _run_query(conn, table: str, column: str, query: str, limit: int = 20) -> list:
    like = f"%{query}%"
    try:
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE {column} LIKE ? LIMIT ?",
            (like, limit)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _table_exists(conn, name: str) -> bool:
    r = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return r is not None


def search_all(conn, query: str, limit: int = 20) -> dict:
    """Search across all Sentinel data. Returns results grouped by type."""
    results = {}

    if _table_exists(conn, "rules"):
        results["rules"] = _run_query(conn, "rules", "text", query, limit)

    if _table_exists(conn, "journal"):
        results["journal"] = _run_query(conn, "journal", "content", query, limit)

    if _table_exists(conn, "reflections"):
        results["reflections"] = _run_query(conn, "reflections", "response", query, limit)

    if _table_exists(conn, "gratitude"):
        results["gratitude"] = _run_query(conn, "gratitude", "text", query, limit)

    if _table_exists(conn, "activity_log"):
        like = f"%{query}%"
        rows = conn.execute("""SELECT * FROM activity_log
                               WHERE app LIKE ? OR title LIKE ? OR url LIKE ? LIMIT ?""",
                            (like, like, like, limit)).fetchall()
        results["activities"] = [dict(r) for r in rows]

    if _table_exists(conn, "goals"):
        results["goals"] = _run_query(conn, "goals", "name", query, limit)

    if _table_exists(conn, "commitments"):
        results["commitments"] = _run_query(conn, "commitments", "text", query, limit)

    if _table_exists(conn, "habits"):
        results["habits"] = _run_query(conn, "habits", "name", query, limit)

    if _table_exists(conn, "chat_messages"):
        results["chat"] = _run_query(conn, "chat_messages", "content", query, limit)

    if _table_exists(conn, "journeys"):
        results["journeys"] = _run_query(conn, "journeys", "name", query, limit)

    if _table_exists(conn, "retros"):
        results["retros"] = _run_query(conn, "retros", "content", query, limit)

    if _table_exists(conn, "audit_log"):
        results["audit"] = _run_query(conn, "audit_log", "action", query, limit)

    # Remove empty categories
    return {k: v for k, v in results.items() if v}


def count_results(conn, query: str) -> int:
    """Count total matches across all tables."""
    results = search_all(conn, query, limit=1000)
    return sum(len(v) for v in results.values())


def search_by_type(conn, query: str, content_type: str, limit: int = 50) -> list:
    """Search a specific content type."""
    table_map = {
        "rule": ("rules", "text"),
        "journal": ("journal", "content"),
        "gratitude": ("gratitude", "text"),
        "habit": ("habits", "name"),
        "goal": ("goals", "name"),
        "reflection": ("reflections", "response"),
    }
    if content_type not in table_map:
        return []
    table, column = table_map[content_type]
    if not _table_exists(conn, table):
        return []
    return _run_query(conn, table, column, query, limit)


def recent_searches(conn) -> list:
    """Get recent searches (from dedicated table)."""
    conn.execute("""CREATE TABLE IF NOT EXISTS search_history (
        id INTEGER PRIMARY KEY, query TEXT, results_count INTEGER, ts REAL
    )""")
    return [dict(r) for r in conn.execute(
        "SELECT * FROM search_history ORDER BY ts DESC LIMIT 20").fetchall()]


def log_search(conn, query: str, results_count: int):
    import time
    conn.execute("""CREATE TABLE IF NOT EXISTS search_history (
        id INTEGER PRIMARY KEY, query TEXT, results_count INTEGER, ts REAL
    )""")
    conn.execute(
        "INSERT INTO search_history (query, results_count, ts) VALUES (?, ?, ?)",
        (query, results_count, time.time()))
    conn.commit()
