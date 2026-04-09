"""Pattern detection — find behavioral patterns."""
from collections import Counter, defaultdict
import datetime as _dt
from . import db


def _distraction_activities(conn):
    rows = conn.execute(
        "SELECT ts, domain, verdict FROM activity_log WHERE ts IS NOT NULL"
    ).fetchall()
    return [dict(r) for r in rows]


def find_daily_patterns(conn) -> dict:
    rows = _distraction_activities(conn)
    distract = Counter()
    productive = Counter()
    for r in rows:
        hr = _dt.datetime.fromtimestamp(r["ts"]).hour
        if r["verdict"] == "block":
            distract[hr] += 1
        elif r["verdict"] == "allow":
            productive[hr] += 1
    return {"distracted_by_hour": dict(distract),
            "productive_by_hour": dict(productive)}


def find_site_pairs(conn) -> list:
    rows = conn.execute(
        "SELECT ts, domain FROM activity_log WHERE domain IS NOT NULL ORDER BY ts"
    ).fetchall()
    pairs = Counter()
    prev = None
    prev_ts = 0
    for r in rows:
        d = r["domain"]
        if prev and d != prev and (r["ts"] - prev_ts) < 600:
            key = tuple(sorted([prev, d]))
            pairs[key] += 1
        prev, prev_ts = d, r["ts"]
    return [{"pair": list(k), "count": v} for k, v in pairs.most_common(10)]


def find_distraction_chains(conn) -> list:
    rows = conn.execute(
        "SELECT ts, domain, verdict FROM activity_log ORDER BY ts"
    ).fetchall()
    chains = []
    cur_chain = []
    for r in rows:
        if r["verdict"] == "block" and r["domain"]:
            cur_chain.append(r["domain"])
        else:
            if len(cur_chain) >= 2:
                chains.append({"sequence": cur_chain, "length": len(cur_chain)})
            cur_chain = []
    if len(cur_chain) >= 2:
        chains.append({"sequence": cur_chain, "length": len(cur_chain)})
    return chains


def find_work_sessions(conn) -> list:
    rows = conn.execute(
        "SELECT ts, domain, verdict FROM activity_log WHERE verdict='allow' ORDER BY ts"
    ).fetchall()
    sessions = []
    start = None
    last = None
    for r in rows:
        if start is None:
            start, last = r["ts"], r["ts"]
        elif r["ts"] - last > 600:
            sessions.append({"start": start, "end": last, "duration_s": last - start})
            start, last = r["ts"], r["ts"]
        else:
            last = r["ts"]
    if start is not None:
        sessions.append({"start": start, "end": last, "duration_s": last - start})
    return [s for s in sessions if s["duration_s"] > 0]


def find_interruptions(conn) -> list:
    rows = conn.execute(
        "SELECT ts, domain, verdict FROM activity_log ORDER BY ts"
    ).fetchall()
    interruptions = []
    for i in range(1, len(rows) - 1):
        p, c, n = rows[i - 1], rows[i], rows[i + 1]
        if p["verdict"] == "allow" and c["verdict"] == "block" and n["verdict"] == "allow":
            interruptions.append({"ts": c["ts"], "domain": c["domain"]})
    return interruptions


def peak_distraction_hour(conn) -> int:
    p = find_daily_patterns(conn)
    distract = p["distracted_by_hour"]
    if not distract:
        return -1
    return max(distract.items(), key=lambda kv: kv[1])[0]


def session_length_distribution(conn) -> dict:
    sessions = find_work_sessions(conn)
    by_hour = defaultdict(list)
    for s in sessions:
        hr = _dt.datetime.fromtimestamp(s["start"]).hour
        by_hour[hr].append(s["duration_s"])
    return {h: round(sum(v) / len(v), 1) for h, v in by_hour.items()}
