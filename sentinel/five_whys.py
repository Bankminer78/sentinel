"""Five Whys — root cause analysis for problems."""
import time, json


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS five_whys (
        id INTEGER PRIMARY KEY, problem TEXT, whys TEXT, root_cause TEXT,
        solution TEXT, created_at REAL
    )""")


def start_analysis(conn, problem: str) -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT INTO five_whys (problem, whys, created_at) VALUES (?, ?, ?)",
        (problem, json.dumps([]), time.time()))
    conn.commit()
    return cur.lastrowid


def add_why(conn, analysis_id: int, why: str) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT whys FROM five_whys WHERE id=?", (analysis_id,)).fetchone()
    if not r:
        return None
    whys = json.loads(r["whys"] or "[]")
    whys.append(why)
    conn.execute("UPDATE five_whys SET whys=? WHERE id=?", (json.dumps(whys), analysis_id))
    conn.commit()
    return {"whys": whys, "count": len(whys)}


def set_root_cause(conn, analysis_id: int, root_cause: str):
    _ensure_table(conn)
    conn.execute(
        "UPDATE five_whys SET root_cause=? WHERE id=?",
        (root_cause, analysis_id))
    conn.commit()


def set_solution(conn, analysis_id: int, solution: str):
    _ensure_table(conn)
    conn.execute("UPDATE five_whys SET solution=? WHERE id=?", (solution, analysis_id))
    conn.commit()


def get_analysis(conn, analysis_id: int) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM five_whys WHERE id=?", (analysis_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    try:
        d["whys"] = json.loads(d.get("whys") or "[]")
    except Exception:
        d["whys"] = []
    return d


def list_analyses(conn, limit: int = 50) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM five_whys ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["whys"] = json.loads(d.get("whys") or "[]")
        except Exception:
            d["whys"] = []
        result.append(d)
    return result


def delete_analysis(conn, analysis_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM five_whys WHERE id=?", (analysis_id,))
    conn.commit()


def incomplete_analyses(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM five_whys WHERE root_cause IS NULL OR root_cause = ''"
    ).fetchall()
    return [dict(r) for r in rows]


def with_solutions(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM five_whys WHERE solution IS NOT NULL AND solution != ''"
    ).fetchall()
    return [dict(r) for r in rows]
