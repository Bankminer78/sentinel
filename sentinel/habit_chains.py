"""Habit chains — chain multiple habits into routines."""
import time, json


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS habit_chains (
        id INTEGER PRIMARY KEY, name TEXT, description TEXT,
        habit_ids TEXT, trigger TEXT, created_at REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS chain_completions (
        id INTEGER PRIMARY KEY, chain_id INTEGER, date TEXT, completed_count INTEGER, ts REAL
    )""")


def create_chain(conn, name: str, habit_ids: list, description: str = "",
                 trigger: str = "") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO habit_chains (name, description, habit_ids, trigger, created_at) VALUES (?, ?, ?, ?, ?)",
        (name, description, json.dumps(habit_ids), trigger, time.time()))
    conn.commit()
    return cur.lastrowid


def get_chain(conn, chain_id: int) -> dict:
    _ensure_tables(conn)
    r = conn.execute("SELECT * FROM habit_chains WHERE id=?", (chain_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    try:
        d["habit_ids"] = json.loads(d.get("habit_ids") or "[]")
    except Exception:
        d["habit_ids"] = []
    return d


def list_chains(conn) -> list:
    _ensure_tables(conn)
    rows = conn.execute("SELECT * FROM habit_chains").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["habit_ids"] = json.loads(d.get("habit_ids") or "[]")
        except Exception:
            d["habit_ids"] = []
        result.append(d)
    return result


def delete_chain(conn, chain_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM habit_chains WHERE id=?", (chain_id,))
    conn.execute("DELETE FROM chain_completions WHERE chain_id=?", (chain_id,))
    conn.commit()


def log_completion(conn, chain_id: int, completed_count: int, date_str: str = None) -> int:
    _ensure_tables(conn)
    from datetime import datetime
    d = date_str or datetime.now().strftime("%Y-%m-%d")
    cur = conn.execute(
        "INSERT INTO chain_completions (chain_id, date, completed_count, ts) VALUES (?, ?, ?, ?)",
        (chain_id, d, completed_count, time.time()))
    conn.commit()
    return cur.lastrowid


def completion_rate(conn, chain_id: int, days: int = 30) -> float:
    _ensure_tables(conn)
    chain = get_chain(conn, chain_id)
    if not chain:
        return 0
    total_habits = len(chain["habit_ids"])
    if total_habits == 0:
        return 0
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    r = conn.execute(
        "SELECT AVG(completed_count) as avg FROM chain_completions WHERE chain_id=? AND date >= ?",
        (chain_id, cutoff)).fetchone()
    avg = r["avg"] if r and r["avg"] else 0
    return round((avg / total_habits) * 100, 1)


def streak(conn, chain_id: int) -> int:
    _ensure_tables(conn)
    chain = get_chain(conn, chain_id)
    if not chain:
        return 0
    total_habits = len(chain["habit_ids"])
    from datetime import datetime, timedelta
    current = datetime.now().date()
    days = 0
    while True:
        dstr = current.strftime("%Y-%m-%d")
        r = conn.execute(
            "SELECT MAX(completed_count) as max FROM chain_completions WHERE chain_id=? AND date=?",
            (chain_id, dstr)).fetchone()
        if r and r["max"] == total_habits:
            days += 1
            current -= timedelta(days=1)
        else:
            if days == 0 and current == datetime.now().date():
                current -= timedelta(days=1)
                continue
            break
    return days


def chains_by_trigger(conn, trigger: str) -> list:
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT * FROM habit_chains WHERE trigger=?", (trigger,)).fetchall()
    return [dict(r) for r in rows]


def total_chains(conn) -> int:
    _ensure_tables(conn)
    r = conn.execute("SELECT COUNT(*) as c FROM habit_chains").fetchone()
    return r["c"] if r else 0
