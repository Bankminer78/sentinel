"""Workflows — pre-defined sequences of actions for common scenarios."""


WORKFLOWS = {
    "start_work_day": {
        "name": "Start Work Day",
        "description": "Morning routine: activate work mode",
        "steps": [
            {"action": "switch_mode", "params": {"mode": "work"}},
            {"action": "start_pomodoro", "params": {"work_minutes": 25}},
            {"action": "log_mood", "params": {"prompt": True}},
            {"action": "morning_briefing", "params": {}},
        ],
    },
    "end_work_day": {
        "name": "End Work Day",
        "description": "Evening routine: wind down",
        "steps": [
            {"action": "switch_mode", "params": {"mode": "relax"}},
            {"action": "evening_reflection", "params": {}},
            {"action": "log_learnings", "params": {"prompt": True}},
            {"action": "gratitude", "params": {"prompt": True}},
        ],
    },
    "deep_focus": {
        "name": "Deep Focus Session",
        "description": "Enter deep work for 90 minutes",
        "steps": [
            {"action": "start_focus", "params": {"duration_minutes": 90, "locked": True}},
            {"action": "enable_dnd", "params": {}},
            {"action": "play_ambient", "params": {"sound_id": "brown_noise"}},
            {"action": "pause_spotify", "params": {}},
        ],
    },
    "break_time": {
        "name": "Break Time",
        "description": "Take a proper break",
        "steps": [
            {"action": "log_water", "params": {"ounces": 8}},
            {"action": "log_eye_break", "params": {}},
            {"action": "stand_up", "params": {}},
        ],
    },
    "weekly_review": {
        "name": "Weekly Review",
        "description": "Saturday review ritual",
        "steps": [
            {"action": "generate_weekly_insights", "params": {}},
            {"action": "review_goals", "params": {}},
            {"action": "create_retro", "params": {}},
            {"action": "plan_next_week", "params": {}},
        ],
    },
}


def list_workflows() -> list:
    return [{"id": k, **v} for k, v in WORKFLOWS.items()]


def get_workflow(workflow_id: str) -> dict:
    return WORKFLOWS.get(workflow_id)


def workflow_steps(workflow_id: str) -> list:
    wf = WORKFLOWS.get(workflow_id)
    return wf["steps"] if wf else []


def count_workflows() -> int:
    return len(WORKFLOWS)


def search_workflows(query: str) -> list:
    q = query.lower()
    return [{"id": k, **v} for k, v in WORKFLOWS.items()
            if q in v["name"].lower() or q in v["description"].lower()]


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS custom_workflows (
        id INTEGER PRIMARY KEY, name TEXT, description TEXT, steps TEXT, created_at REAL
    )""")


def create_custom_workflow(conn, name: str, description: str, steps: list) -> int:
    _ensure_table(conn)
    import time, json
    cur = conn.execute(
        "INSERT INTO custom_workflows (name, description, steps, created_at) VALUES (?, ?, ?, ?)",
        (name, description, json.dumps(steps), time.time()))
    conn.commit()
    return cur.lastrowid


def get_custom_workflows(conn) -> list:
    _ensure_table(conn)
    import json
    rows = conn.execute("SELECT * FROM custom_workflows").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["steps"] = json.loads(d.get("steps") or "[]")
        except Exception:
            d["steps"] = []
        result.append(d)
    return result


def delete_custom_workflow(conn, workflow_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM custom_workflows WHERE id=?", (workflow_id,))
    conn.commit()
