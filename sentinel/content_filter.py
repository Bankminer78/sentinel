"""Content filter — filter page content by keywords."""
import re, time


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS content_filters (
        id INTEGER PRIMARY KEY, keyword TEXT, match_type TEXT,
        action TEXT, case_sensitive INTEGER DEFAULT 0, created_at REAL
    )""")


def add_filter(conn, keyword: str, action: str = "block",
               match_type: str = "contains", case_sensitive: bool = False) -> int:
    _ensure_table(conn)
    cur = conn.execute(
        """INSERT INTO content_filters (keyword, match_type, action, case_sensitive, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (keyword, match_type, action, 1 if case_sensitive else 0, time.time()))
    conn.commit()
    return cur.lastrowid


def get_filters(conn) -> list:
    _ensure_table(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM content_filters").fetchall()]


def delete_filter(conn, filter_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM content_filters WHERE id=?", (filter_id,))
    conn.commit()


def matches_filter(content: str, filter_rule: dict) -> bool:
    """Check if content matches a filter rule."""
    text = content if filter_rule.get("case_sensitive") else content.lower()
    keyword = filter_rule["keyword"] if filter_rule.get("case_sensitive") else filter_rule["keyword"].lower()
    match_type = filter_rule.get("match_type", "contains")
    if match_type == "contains":
        return keyword in text
    if match_type == "exact":
        return keyword == text.strip()
    if match_type == "starts_with":
        return text.startswith(keyword)
    if match_type == "ends_with":
        return text.endswith(keyword)
    if match_type == "regex":
        try:
            return bool(re.search(keyword, text))
        except Exception:
            return False
    return False


def check_content(conn, content: str) -> dict:
    """Check content against all filters."""
    filters = get_filters(conn)
    matched = []
    for f in filters:
        if matches_filter(content, f):
            matched.append(f)
    return {
        "matched": matched,
        "should_block": any(f["action"] == "block" for f in matched),
        "should_warn": any(f["action"] == "warn" for f in matched),
    }


def count_filters(conn) -> int:
    _ensure_table(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM content_filters").fetchone()
    return r["c"] if r else 0


def filters_by_action(conn, action: str) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM content_filters WHERE action=?", (action,)).fetchall()
    return [dict(r) for r in rows]


def test_filter(keyword: str, content: str, match_type: str = "contains",
                case_sensitive: bool = False) -> bool:
    """Test a filter without saving it."""
    rule = {
        "keyword": keyword,
        "match_type": match_type,
        "case_sensitive": case_sensitive,
    }
    return matches_filter(content, rule)
