"""Alert system — trigger alerts when thresholds crossed."""
import time
from . import stats


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY, name TEXT, condition TEXT,
        threshold REAL, action TEXT, muted_until REAL, active INTEGER DEFAULT 1
    )""")


def create_alert(conn, name: str, condition: str, threshold: float,
                 action: str = "notify") -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO alerts (name, condition, threshold, action, muted_until, active) "
        "VALUES (?, ?, ?, ?, 0, 1)",
        (name, condition, threshold, action))
    conn.commit()
    return cur.lastrowid


def get_alerts(conn) -> list:
    _ensure_table(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM alerts ORDER BY id").fetchall()]


def delete_alert(conn, alert_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM alerts WHERE id=?", (alert_id,))
    conn.commit()


def mute_alert(conn, alert_id: int, minutes: int):
    _ensure_table(conn)
    until = time.time() + minutes * 60
    conn.execute("UPDATE alerts SET muted_until=? WHERE id=?", (until, alert_id))
    conn.commit()


def _evaluate(conn, alert: dict) -> bool:
    cond = alert["condition"]
    th = alert["threshold"]
    if cond == "score_below":
        return stats.calculate_score(conn) < th
    if cond == "time_spent_over":
        b = stats.get_daily_breakdown(conn)
        return b["distracting"] > th
    if cond == "streak_about_to_break":
        from . import habits
        for h in habits.get_habits(conn):
            s = habits.get_habit_stats(conn, h["id"])
            if s["current_streak"] >= th:
                todays = [t for t in habits.get_todays_habits(conn) if t["id"] == h["id"]]
                if todays and not todays[0]["done"]:
                    return True
        return False
    return False


async def check_alerts(conn, api_key: str = "") -> list:
    _ensure_table(conn)
    now = time.time()
    triggered = []
    for a in get_alerts(conn):
        if not a["active"]:
            continue
        if a["muted_until"] and a["muted_until"] > now:
            continue
        if _evaluate(conn, a):
            triggered.append({
                "id": a["id"], "name": a["name"],
                "condition": a["condition"], "threshold": a["threshold"],
                "action": a["action"],
            })
    return triggered
