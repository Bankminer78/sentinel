"""Medication reminders — track meds and adherence."""
import time
from datetime import datetime, timedelta


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS medications (
        id INTEGER PRIMARY KEY, name TEXT, dosage TEXT, frequency TEXT,
        times_per_day INTEGER, notes TEXT, active INTEGER DEFAULT 1, added_at REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS medication_log (
        id INTEGER PRIMARY KEY, medication_id INTEGER, date TEXT, ts REAL
    )""")


def add_medication(conn, name: str, dosage: str = "", frequency: str = "daily",
                   times_per_day: int = 1, notes: str = "") -> int:
    _ensure_tables(conn)
    cur = conn.execute(
        "INSERT INTO medications (name, dosage, frequency, times_per_day, notes, added_at) VALUES (?, ?, ?, ?, ?, ?)",
        (name, dosage, frequency, times_per_day, notes, time.time()))
    conn.commit()
    return cur.lastrowid


def get_medications(conn, active_only: bool = True) -> list:
    _ensure_tables(conn)
    q = "SELECT * FROM medications"
    if active_only:
        q += " WHERE active=1"
    return [dict(r) for r in conn.execute(q).fetchall()]


def deactivate_medication(conn, med_id: int):
    _ensure_tables(conn)
    conn.execute("UPDATE medications SET active=0 WHERE id=?", (med_id,))
    conn.commit()


def log_taken(conn, med_id: int) -> int:
    _ensure_tables(conn)
    date_str = datetime.now().strftime("%Y-%m-%d")
    cur = conn.execute(
        "INSERT INTO medication_log (medication_id, date, ts) VALUES (?, ?, ?)",
        (med_id, date_str, time.time()))
    conn.commit()
    return cur.lastrowid


def taken_today(conn, med_id: int) -> int:
    _ensure_tables(conn)
    today = datetime.now().strftime("%Y-%m-%d")
    r = conn.execute(
        "SELECT COUNT(*) as c FROM medication_log WHERE medication_id=? AND date=?",
        (med_id, today)).fetchone()
    return r["c"]


def adherence_rate(conn, med_id: int, days: int = 30) -> float:
    _ensure_tables(conn)
    med = conn.execute("SELECT * FROM medications WHERE id=?", (med_id,)).fetchone()
    if not med:
        return 0
    expected = med["times_per_day"] * days
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    r = conn.execute(
        "SELECT COUNT(*) as c FROM medication_log WHERE medication_id=? AND date >= ?",
        (med_id, cutoff)).fetchone()
    actual = r["c"]
    return round((actual / expected * 100) if expected > 0 else 0, 1)


def missed_doses_today(conn) -> list:
    _ensure_tables(conn)
    meds = get_medications(conn)
    missed = []
    for m in meds:
        taken = taken_today(conn, m["id"])
        if taken < m["times_per_day"]:
            missed.append({**m, "taken": taken, "missing": m["times_per_day"] - taken})
    return missed


def delete_medication(conn, med_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM medications WHERE id=?", (med_id,))
    conn.execute("DELETE FROM medication_log WHERE medication_id=?", (med_id,))
    conn.commit()


def medication_streak(conn, med_id: int) -> int:
    """Consecutive days meeting the required doses."""
    _ensure_tables(conn)
    med = conn.execute("SELECT * FROM medications WHERE id=?", (med_id,)).fetchone()
    if not med:
        return 0
    target = med["times_per_day"]
    current = datetime.now().date()
    days = 0
    while True:
        dstr = current.strftime("%Y-%m-%d")
        r = conn.execute(
            "SELECT COUNT(*) as c FROM medication_log WHERE medication_id=? AND date=?",
            (med_id, dstr)).fetchone()
        if r["c"] >= target:
            days += 1
            current -= timedelta(days=1)
        else:
            break
    return days
