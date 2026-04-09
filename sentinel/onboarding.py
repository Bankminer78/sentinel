"""First-time onboarding — interactive setup wizard."""
from . import db, stats as stats_mod, habits as habits_mod

_CONFIG_KEY = "onboarded"

PERSONAS = ("student", "developer", "knowledge_worker", "parent")

_RULES = {
    "student": [
        "Block social media and streaming while studying",
        "Block gaming sites during study hours (9am-6pm weekdays)",
    ],
    "developer": [
        "Block social media during work hours (9am-5pm weekdays)",
        "Block streaming sites during work hours (9am-5pm weekdays)",
    ],
    "knowledge_worker": [
        "Block social media during work hours (9am-5pm weekdays)",
        "Block shopping sites during work hours (9am-5pm weekdays)",
    ],
    "parent": [
        "Block adult content at all times",
        "Block streaming and gaming from 9pm to 7am every day",
    ],
}

_GOALS = {
    "student": [
        {"name": "study focus", "target_type": "max_seconds", "target_value": 1800, "category": "social"},
    ],
    "developer": [
        {"name": "deep work", "target_type": "min_seconds", "target_value": 14400, "category": "productive"},
    ],
    "knowledge_worker": [
        {"name": "limit social", "target_type": "max_seconds", "target_value": 900, "category": "social"},
    ],
    "parent": [
        {"name": "no adult", "target_type": "zero", "target_value": 0, "category": "adult"},
    ],
}

_HABITS = {
    "student": ["Read for 30 minutes", "Review notes"],
    "developer": ["Morning standup review", "Write one code snippet"],
    "knowledge_worker": ["Inbox zero", "Daily planning"],
    "parent": ["Screen-free family time", "Early bedtime"],
}


def is_first_run(conn) -> bool:
    return db.get_config(conn, _CONFIG_KEY) != "1"


def mark_onboarded(conn):
    db.set_config(conn, _CONFIG_KEY, "1")


def _validate(persona: str):
    if persona not in PERSONAS:
        raise ValueError(f"unknown persona: {persona}")


def suggest_initial_rules(persona: str) -> list[str]:
    _validate(persona)
    return list(_RULES[persona])


def suggest_initial_goals(persona: str) -> list[dict]:
    _validate(persona)
    return [dict(g) for g in _GOALS[persona]]


def suggest_initial_habits(persona: str) -> list[str]:
    _validate(persona)
    return list(_HABITS[persona])


def create_persona_setup(conn, persona: str) -> dict:
    """Apply a persona setup: rules + goals + habits. Marks onboarded."""
    _validate(persona)
    rule_ids = [db.add_rule(conn, t, {}) for t in suggest_initial_rules(persona)]
    goal_ids = [
        stats_mod.add_goal(conn, g["name"], g["target_type"], g["target_value"], g["category"])
        for g in suggest_initial_goals(persona)
    ]
    habit_ids = [habits_mod.add_habit(conn, h) for h in suggest_initial_habits(persona)]
    mark_onboarded(conn)
    return {
        "persona": persona,
        "rule_ids": rule_ids,
        "goal_ids": goal_ids,
        "habit_ids": habit_ids,
    }


def list_personas() -> list[str]:
    return list(PERSONAS)
