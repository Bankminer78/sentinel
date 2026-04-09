"""User journey — visualize the user's growth over time."""
import time
from datetime import datetime, timedelta


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS journey_milestones (
        id INTEGER PRIMARY KEY, title TEXT, description TEXT,
        category TEXT, ts REAL
    )""")


def record_milestone(conn, title: str, description: str = "", category: str = "general") -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO journey_milestones (title, description, category, ts) VALUES (?, ?, ?, ?)",
        (title, description, category, time.time()))
    conn.commit()
    return cur.lastrowid


def get_milestones(conn, category: str = None, limit: int = 50) -> list:
    _ensure_table(conn)
    if category:
        rows = conn.execute(
            "SELECT * FROM journey_milestones WHERE category=? ORDER BY ts DESC LIMIT ?",
            (category, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM journey_milestones ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def delete_milestone(conn, milestone_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM journey_milestones WHERE id=?", (milestone_id,))
    conn.commit()


def journey_timeline(conn, days: int = 90) -> list:
    """Timeline of milestones + automatic milestones from other modules."""
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    manual = [dict(r) for r in conn.execute(
        "SELECT *, 'manual' as source FROM journey_milestones WHERE ts > ? ORDER BY ts DESC",
        (cutoff,)).fetchall()]
    # Auto: first_day, achievements, etc.
    auto = []
    try:
        ach_rows = conn.execute(
            "SELECT id, unlocked_at FROM achievements WHERE unlocked_at > ?", (cutoff,)).fetchall()
        for r in ach_rows:
            auto.append({
                "title": f"Unlocked: {r['id']}",
                "category": "achievement",
                "ts": r["unlocked_at"],
                "source": "achievements",
            })
    except Exception:
        pass
    try:
        rule_rows = conn.execute(
            "SELECT text, created_at FROM rules WHERE created_at > ? ORDER BY created_at DESC LIMIT 10",
            (cutoff,)).fetchall()
        for r in rule_rows:
            auto.append({
                "title": f"Added rule: {r['text'][:50]}",
                "category": "rule",
                "ts": r["created_at"] or 0,
                "source": "rules",
            })
    except Exception:
        pass
    combined = manual + auto
    return sorted(combined, key=lambda m: m.get("ts") or 0, reverse=True)


def growth_chart(conn, days: int = 90) -> list:
    """Get daily quantified self scores over the past N days for charting."""
    from . import quantified_self
    today = datetime.now().date()
    scores = []
    for i in range(days):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        try:
            result = quantified_self.get_daily_score(conn, d)
            scores.append({"date": d, "score": result.get("score", 0)})
        except Exception:
            scores.append({"date": d, "score": 0})
    return list(reversed(scores))


def streak_record(conn) -> dict:
    """Longest streaks across all tracked activities."""
    _ensure_table(conn)
    streaks = {}
    # From streaks table
    try:
        rows = conn.execute("SELECT * FROM streaks").fetchall()
        for r in rows:
            streaks[r["goal_name"]] = {"current": r["current"], "longest": r["longest"]}
    except Exception:
        pass
    return streaks


def growth_summary(conn) -> dict:
    _ensure_table(conn)
    milestone_count = conn.execute(
        "SELECT COUNT(*) as c FROM journey_milestones").fetchone()["c"]
    return {
        "milestones": milestone_count,
        "streaks": streak_record(conn),
    }
