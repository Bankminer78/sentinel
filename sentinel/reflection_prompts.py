"""Curated reflection prompts — 100+ questions for deeper thinking."""
import random
from datetime import datetime


PROMPTS = {
    "morning": [
        "What is your one priority for today?",
        "What would make today a great day?",
        "What are you grateful for this morning?",
        "What is one small act of kindness you can do today?",
        "Who will you show up for today?",
        "What's one thing you're looking forward to?",
        "What intention do you want to set for the day?",
        "How do you want to feel at the end of today?",
        "What's one obstacle you might face, and how will you handle it?",
        "What would your future self want you to do today?",
    ],
    "evening": [
        "What went well today?",
        "What could have gone better?",
        "What did you learn?",
        "Who did you help today?",
        "What are you grateful for from today?",
        "What are you proud of?",
        "What did you find difficult?",
        "Was there a moment of joy?",
        "How did you fall short of your ideals?",
        "What would you do differently?",
    ],
    "weekly": [
        "What were your biggest wins this week?",
        "What's one thing you're letting go of?",
        "What patterns did you notice?",
        "What energized you?",
        "What drained you?",
        "What relationships were you grateful for?",
        "What did you learn about yourself?",
        "What didn't you have time for?",
        "What do you want to do more of next week?",
        "What do you want to do less of next week?",
    ],
    "gratitude": [
        "What three things are you grateful for?",
        "Who's a person you're grateful for today?",
        "What's a simple pleasure you enjoyed?",
        "What's something you take for granted?",
        "What's a part of your body you're grateful for?",
        "What's a skill you're grateful to have?",
        "What's something beautiful you saw today?",
        "What's a memory you're grateful for?",
        "What's something you can do today that you couldn't a year ago?",
        "What's a small thing that made your day better?",
    ],
    "growth": [
        "What's one area you want to grow in?",
        "What's a belief you're questioning?",
        "What's something you're afraid to admit?",
        "What's a pattern you want to break?",
        "What would you do if you weren't afraid?",
        "What's an opinion you held that you've changed?",
        "What's a risk worth taking?",
        "What are you avoiding, and why?",
        "What does success mean to you?",
        "What would make the next year the best year of your life?",
    ],
    "values": [
        "What are your top 3 values?",
        "How did you live by your values today?",
        "Where did you compromise your values?",
        "What do you want to be known for?",
        "What kind of person do you want to be?",
        "What matters most to you right now?",
        "What are you unwilling to sacrifice?",
        "What's your why?",
        "What would your eulogy say?",
        "What legacy do you want to leave?",
    ],
    "relationships": [
        "Who did you connect with today?",
        "Who needs your attention?",
        "Who have you been ignoring?",
        "What relationship needs mending?",
        "Who brings out the best in you?",
        "Who drains your energy?",
        "What's something kind you can say?",
        "Who are you grateful to have in your life?",
        "What did you learn from someone today?",
        "Who could you call or text right now?",
    ],
    "work": [
        "What's your most impactful work this week?",
        "What did you procrastinate on?",
        "What's one thing you'd do if you had more courage?",
        "What's draining your focus?",
        "What are you building?",
        "What would make your work meaningful?",
        "What skill would most help your career?",
        "What feedback have you ignored?",
        "What project should you kill?",
        "What would you work on if money didn't matter?",
    ],
    "health": [
        "How does your body feel?",
        "What did you eat today?",
        "How much did you move?",
        "Are you sleeping enough?",
        "What's stressing you out?",
        "When did you last really rest?",
        "What's one healthy habit you want to start?",
        "Are you drinking enough water?",
        "How's your posture right now?",
        "When did you last see a doctor?",
    ],
    "creativity": [
        "What did you create today?",
        "What inspired you?",
        "What's one creative risk you could take?",
        "What would you make if you couldn't fail?",
        "What's a problem you could solve creatively?",
        "What's something you're curious about?",
        "What's blocking your creativity?",
        "What's a small creative act you could do now?",
        "Whose work inspires you?",
        "What medium do you want to try?",
    ],
}


def get_prompt(category: str = None) -> str:
    """Get a random prompt from a category."""
    if category and category in PROMPTS:
        return random.choice(PROMPTS[category])
    all_prompts = []
    for prompts in PROMPTS.values():
        all_prompts.extend(prompts)
    return random.choice(all_prompts)


def get_categories() -> list:
    return list(PROMPTS.keys())


def get_daily_prompt(category: str = None) -> str:
    """Prompt that stays the same throughout the day."""
    seed = datetime.now().strftime("%Y-%m-%d") + (category or "")
    random.seed(seed)
    return get_prompt(category)


def get_prompts_for_category(category: str) -> list:
    return PROMPTS.get(category, [])


def total_prompts() -> int:
    return sum(len(v) for v in PROMPTS.values())


def prompts_for_time_of_day() -> list:
    hour = datetime.now().hour
    if hour < 10:
        return PROMPTS["morning"]
    if hour >= 20:
        return PROMPTS["evening"]
    return PROMPTS["gratitude"]
