"""Advanced schedules — holidays, exceptions, recurring patterns."""
from datetime import datetime, timedelta


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS holidays (
        id INTEGER PRIMARY KEY, name TEXT, date TEXT UNIQUE
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS schedule_exceptions (
        id INTEGER PRIMARY KEY, schedule_id INTEGER, date TEXT, action TEXT
    )""")


def add_holiday(conn, name: str, date_str: str) -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT OR REPLACE INTO holidays (name, date) VALUES (?, ?)", (name, date_str))
    conn.commit()
    return cur.lastrowid


def get_holidays(conn) -> list:
    _ensure_tables(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM holidays ORDER BY date").fetchall()]


def delete_holiday(conn, holiday_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM holidays WHERE id=?", (holiday_id,))
    conn.commit()


def is_holiday(conn, date_str: str = None) -> bool:
    _ensure_tables(conn)
    d = date_str or datetime.now().strftime("%Y-%m-%d")
    return conn.execute("SELECT 1 FROM holidays WHERE date=?", (d,)).fetchone() is not None


def add_exception(conn, schedule_id: int, date_str: str, action: str = "skip") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO schedule_exceptions (schedule_id, date, action) VALUES (?, ?, ?)",
        (schedule_id, date_str, action))
    conn.commit()
    return cur.lastrowid


def get_exceptions(conn, schedule_id: int = None) -> list:
    _ensure_tables(conn)
    if schedule_id:
        rows = conn.execute(
            "SELECT * FROM schedule_exceptions WHERE schedule_id=?", (schedule_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM schedule_exceptions").fetchall()
    return [dict(r) for r in rows]


def is_exception(conn, schedule_id: int, date_str: str = None) -> bool:
    _ensure_tables(conn)
    d = date_str or datetime.now().strftime("%Y-%m-%d")
    return conn.execute(
        "SELECT 1 FROM schedule_exceptions WHERE schedule_id=? AND date=?",
        (schedule_id, d)).fetchone() is not None


def delete_exception(conn, exception_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM schedule_exceptions WHERE id=?", (exception_id,))
    conn.commit()


def next_n_days_schedule(conn, schedule_id: int, n: int = 7) -> list:
    """Preview: which of the next N days is the schedule active?"""
    _ensure_tables(conn)
    today = datetime.now().date()
    result = []
    for i in range(n):
        d = today + timedelta(days=i)
        dstr = d.strftime("%Y-%m-%d")
        active = True
        reason = "active"
        if is_holiday(conn, dstr):
            active = False
            reason = "holiday"
        elif is_exception(conn, schedule_id, dstr):
            active = False
            reason = "exception"
        result.append({"date": dstr, "day": d.strftime("%A"), "active": active, "reason": reason})
    return result
