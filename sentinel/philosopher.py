"""Stoic-style philosophical reflections and quotes."""
import random
from datetime import datetime
from . import db


STOIC_QUOTES = [
    ("You have power over your mind, not outside events.", "Marcus Aurelius"),
    ("Waste no more time arguing what a good man should be. Be one.", "Marcus Aurelius"),
    ("He suffers more than necessary, who suffers before it is necessary.", "Seneca"),
    ("It is not the man who has too little, but the man who craves more, that is poor.", "Seneca"),
    ("Wealth consists not in having great possessions, but in having few wants.", "Epictetus"),
    ("First say to yourself what you would be; and then do what you have to do.", "Epictetus"),
    ("If it is not right do not do it, if it is not true do not say it.", "Marcus Aurelius"),
    ("Man conquers the world by conquering himself.", "Zeno"),
    ("The whole future lies in uncertainty: live immediately.", "Seneca"),
    ("Sometimes even to live is an act of courage.", "Seneca"),
    ("Difficulties strengthen the mind, as labor does the body.", "Seneca"),
    ("He who fears death will never do anything worthy of a living man.", "Seneca"),
    ("No man is free who is not master of himself.", "Epictetus"),
    ("Everything we hear is an opinion, not a fact.", "Marcus Aurelius"),
    ("Begin at once to live.", "Marcus Aurelius"),
]

MORNING_PROMPTS = [
    "What is your one priority for today?",
    "What would make today a great day?",
    "What are you grateful for this morning?",
    "What obstacle might you face, and how will you handle it?",
    "Who will you show up for today?",
]

EVENING_PROMPTS = [
    "What went well today?",
    "What could have gone better?",
    "What did you learn?",
    "What are you grateful for from today?",
    "How did you fall short of your ideals?",
]


def daily_quote() -> tuple:
    """Daily quote (same quote throughout the day)."""
    seed = datetime.now().strftime("%Y-%m-%d")
    random.seed(seed)
    return random.choice(STOIC_QUOTES)


def random_quote() -> tuple:
    return random.choice(STOIC_QUOTES)


def morning_prompt() -> str:
    return random.choice(MORNING_PROMPTS)


def evening_prompt() -> str:
    return random.choice(EVENING_PROMPTS)


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS reflections (
        id INTEGER PRIMARY KEY, prompt TEXT, response TEXT, ts REAL
    )""")


def save_reflection(conn, prompt: str, response: str) -> int:
    _ensure_table(conn)
    import time
    cur = conn.execute(
        "INSERT INTO reflections (prompt, response, ts) VALUES (?, ?, ?)",
        (prompt, response, time.time()))
    conn.commit()
    return cur.lastrowid


def get_reflections(conn, limit: int = 30) -> list:
    _ensure_table(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM reflections ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()]


def search_reflections(conn, query: str) -> list:
    _ensure_table(conn)
    like = f"%{query}%"
    return [dict(r) for r in conn.execute(
        "SELECT * FROM reflections WHERE prompt LIKE ? OR response LIKE ?",
        (like, like)).fetchall()]
