"""Leaderboards — compare scores with accountability partners."""
from datetime import datetime, timedelta


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS leaderboard_scores (
        user TEXT, date TEXT, score REAL, PRIMARY KEY (user, date)
    )""")


def record_score(conn, user: str, date_str: str, score: float):
    _ensure_table(conn)
    conn.execute("INSERT OR REPLACE INTO leaderboard_scores (user, date, score) VALUES (?, ?, ?)",
                 (user, date_str, score))
    conn.commit()


def get_leaderboard(conn, days: int = 7) -> list:
    _ensure_table(conn)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT user, AVG(score) as avg_score, COUNT(*) as days_tracked
        FROM leaderboard_scores WHERE date >= ? GROUP BY user ORDER BY avg_score DESC
    """, (cutoff,)).fetchall()
    return [{"user": r["user"], "avg_score": round(r["avg_score"], 1),
             "days_tracked": r["days_tracked"]} for r in rows]


def get_user_stats(conn, user: str) -> dict:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT score FROM leaderboard_scores WHERE user=? ORDER BY date DESC LIMIT 30",
        (user,)).fetchall()
    if not rows:
        return {"user": user, "avg_score": 0, "best_score": 0, "days_tracked": 0}
    scores = [r["score"] for r in rows]
    return {
        "user": user, "days_tracked": len(scores),
        "avg_score": round(sum(scores) / len(scores), 1),
        "best_score": round(max(scores), 1),
        "worst_score": round(min(scores), 1),
    }
