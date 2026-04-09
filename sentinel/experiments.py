"""Self-experiments — try a change, measure impact."""
import time
import datetime as _dt
from . import classifier, stats


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS experiments (
        id INTEGER PRIMARY KEY, name TEXT, hypothesis TEXT,
        start_ts REAL, end_ts REAL, status TEXT DEFAULT 'active',
        baseline_avg REAL, during_avg REAL
    )""")


def _avg_score(conn, start_ts: float, end_ts: float) -> float:
    start_d = _dt.date.fromtimestamp(start_ts)
    end_d = _dt.date.fromtimestamp(end_ts)
    scores = []
    d = start_d
    while d <= end_d:
        b = stats.get_daily_breakdown(conn, d.strftime("%Y-%m-%d"))
        if b["total"] > 0:
            scores.append(100.0 * b["productive"] / b["total"])
        d += _dt.timedelta(days=1)
    return round(sum(scores) / len(scores), 2) if scores else 0.0


def start_experiment(conn, name: str, hypothesis: str, duration_days: int) -> int:
    _ensure_table(conn)
    now = time.time()
    baseline = _avg_score(conn, now - 14 * 86400, now)
    end_ts = now + duration_days * 86400
    cur = conn.execute(
        "INSERT INTO experiments (name, hypothesis, start_ts, end_ts, status, baseline_avg) "
        "VALUES (?, ?, ?, ?, 'active', ?)",
        (name, hypothesis, now, end_ts, baseline))
    conn.commit()
    return cur.lastrowid


def end_experiment(conn, experiment_id: int):
    _ensure_table(conn)
    e = get_experiment(conn, experiment_id)
    if not e:
        return
    now = time.time()
    during = _avg_score(conn, e["start_ts"], now)
    conn.execute(
        "UPDATE experiments SET status='ended', end_ts=?, during_avg=? WHERE id=?",
        (now, during, experiment_id))
    conn.commit()


def get_experiment(conn, experiment_id: int) -> dict:
    _ensure_table(conn)
    r = conn.execute("SELECT * FROM experiments WHERE id=?", (experiment_id,)).fetchone()
    return dict(r) if r else None


def list_experiments(conn, status: str = None) -> list:
    _ensure_table(conn)
    if status:
        rows = conn.execute(
            "SELECT * FROM experiments WHERE status=? ORDER BY id DESC", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM experiments ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def experiment_results(conn, experiment_id: int) -> dict:
    e = get_experiment(conn, experiment_id)
    if not e:
        return {}
    during = e["during_avg"]
    if during is None:
        during = _avg_score(conn, e["start_ts"], min(time.time(), e["end_ts"] or time.time()))
    baseline = e["baseline_avg"] or 0.0
    delta = round(during - baseline, 2)
    return {
        "experiment_id": experiment_id,
        "name": e["name"],
        "hypothesis": e["hypothesis"],
        "baseline_avg": baseline,
        "during_avg": during,
        "delta": delta,
        "improved": delta > 0,
        "status": e["status"],
    }


async def analyze_experiment(conn, experiment_id: int, api_key: str) -> str:
    r = experiment_results(conn, experiment_id)
    if not r:
        return ""
    prompt = (
        f"Analyze this self-experiment in 3-4 sentences. Hypothesis: {r['hypothesis']}. "
        f"Baseline score: {r['baseline_avg']}. During: {r['during_avg']}. "
        f"Delta: {r['delta']}. Was the hypothesis supported?"
    )
    return await classifier.call_gemini(api_key, prompt, max_tokens=250)
