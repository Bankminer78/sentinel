"""Import/export rules, goals, partners, config as JSON."""
import json, time
from sentinel import db, partners as partners_mod


def export_rules(conn) -> str:
    rules = db.get_rules(conn, active_only=False)
    out = [{"text": r["text"], "parsed": r.get("parsed") or "{}",
            "action": r.get("action") or "block",
            "active": bool(r.get("active", 1))} for r in rules]
    return json.dumps({"version": 1, "rules": out}, indent=2)


def import_rules(conn, json_str: str) -> int:
    try:
        data = json.loads(json_str) if isinstance(json_str, str) else json_str
    except json.JSONDecodeError:
        return 0
    rules = data.get("rules", []) if isinstance(data, dict) else data
    count = 0
    for r in rules:
        if not isinstance(r, dict) or not r.get("text"):
            continue
        parsed = r.get("parsed") or {}
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except json.JSONDecodeError:
                parsed = {}
        db.add_rule(conn, r["text"], parsed)
        count += 1
    return count


def export_all(conn) -> dict:
    rules = [{"text": r["text"], "parsed": r.get("parsed") or "{}",
              "action": r.get("action") or "block",
              "active": bool(r.get("active", 1))}
             for r in db.get_rules(conn, active_only=False)]
    goals_rows = conn.execute("SELECT * FROM goals").fetchall()
    goals = [{"name": g["name"], "target_type": g["target_type"],
              "target_value": g["target_value"], "category": g["category"]}
             for g in goals_rows]
    parts = [{"name": p["name"], "contact": p["contact"], "method": p["method"]}
             for p in partners_mod.get_partners(conn)]
    cfg_rows = conn.execute("SELECT key, value FROM config").fetchall()
    config = {r["key"]: r["value"] for r in cfg_rows if r["key"] != "gemini_api_key"}
    return {"version": 1, "exported_at": time.time(),
            "rules": rules, "goals": goals, "partners": parts, "config": config}


def import_all(conn, data) -> dict:
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return {"rules": 0, "goals": 0, "partners": 0, "config": 0}
    if not isinstance(data, dict):
        return {"rules": 0, "goals": 0, "partners": 0, "config": 0}
    counts = {"rules": 0, "goals": 0, "partners": 0, "config": 0}
    counts["rules"] = import_rules(conn, {"rules": data.get("rules", [])})
    for g in data.get("goals", []) or []:
        if g.get("name") and g.get("target_type"):
            conn.execute(
                "INSERT INTO goals (name,target_type,target_value,category,created_at) VALUES (?,?,?,?,?)",
                (g["name"], g["target_type"], int(g.get("target_value") or 0),
                 g.get("category"), time.time()))
            counts["goals"] += 1
    for p in data.get("partners", []) or []:
        if p.get("name") and p.get("contact"):
            partners_mod.add_partner(conn, p["name"], p["contact"], p.get("method", "webhook"))
            counts["partners"] += 1
    for k, v in (data.get("config") or {}).items():
        if k != "gemini_api_key":
            db.set_config(conn, k, v)
            counts["config"] += 1
    conn.commit()
    return counts
