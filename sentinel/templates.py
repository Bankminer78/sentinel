"""Predefined rule templates — enable common setups in one command."""
from sentinel import db


TEMPLATES = {
    "work_focus": {
        "name": "Work Focus",
        "description": "Block social media and streaming during work hours",
        "rules": [
            {"text": "Block all social media during work hours (9am-5pm weekdays)"},
            {"text": "Block streaming sites during work hours (9am-5pm weekdays)"},
        ],
    },
    "deep_work": {
        "name": "Deep Work",
        "description": "Block all distractions for deep work sessions",
        "rules": [
            {"text": "Block social media, streaming, and gaming sites at all times"},
            {"text": "Block news sites during work hours (9am-5pm weekdays)"},
        ],
    },
    "no_porn": {
        "name": "No Porn",
        "description": "Block all adult content permanently",
        "rules": [
            {"text": "Block all adult and pornographic websites at all times"},
        ],
    },
    "no_shopping": {
        "name": "No Shopping",
        "description": "Block shopping sites to curb impulse buying",
        "rules": [
            {"text": "Block shopping and e-commerce sites at all times"},
        ],
    },
    "study_mode": {
        "name": "Study Mode",
        "description": "Block distractions to focus on studying",
        "rules": [
            {"text": "Block social media and streaming while studying"},
            {"text": "Block gaming sites while studying"},
        ],
    },
    "sleep_hygiene": {
        "name": "Sleep Hygiene",
        "description": "Block screens late at night for better sleep",
        "rules": [
            {"text": "Block social media, streaming, and gaming from 10pm to 6am every day"},
        ],
    },
    "detox": {
        "name": "Digital Detox",
        "description": "Block everything distracting for a day",
        "rules": [
            {"text": "Block all social media, streaming, gaming, shopping, and adult sites today"},
        ],
    },
}


def list_templates() -> list[dict]:
    return [{"key": k, "name": v["name"], "description": v["description"],
             "rule_count": len(v["rules"])} for k, v in TEMPLATES.items()]


def get_template(name: str) -> dict | None:
    return TEMPLATES.get(name)


def apply_template(conn, template_name: str) -> list[int]:
    tpl = TEMPLATES.get(template_name)
    if not tpl:
        raise ValueError(f"unknown template: {template_name}")
    return [db.add_rule(conn, r["text"], {}) for r in tpl["rules"]]
