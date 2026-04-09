"""Motivational messages — quotes, reminders, encouragement."""
import random, datetime as _dt
from sentinel import db, classifier

QUOTES = [
    ("Discipline equals freedom.", "Jocko Willink"),
    ("The successful warrior is the average person with laser-like focus.", "Bruce Lee"),
    ("You do not rise to the level of your goals. You fall to the level of your systems.", "James Clear"),
    ("It is the constant and determined effort that breaks down resistance and sweeps away all obstacles.", "Claude M. Bristol"),
    ("Concentrate all your thoughts upon the work at hand.", "Alexander Graham Bell"),
    ("The shorter way to do many things is to do only one thing at a time.", "Mozart"),
    ("Focus on being productive instead of busy.", "Tim Ferriss"),
    ("What you do every day matters more than what you do once in a while.", "Gretchen Rubin"),
    ("Well done is better than well said.", "Benjamin Franklin"),
    ("The secret of getting ahead is getting started.", "Mark Twain"),
    ("Action is the foundational key to all success.", "Pablo Picasso"),
    ("Amateurs sit and wait for inspiration. The rest of us just get up and go to work.", "Stephen King"),
    ("Your future is created by what you do today, not tomorrow.", "Robert Kiyosaki"),
    ("Do the hard jobs first. The easy jobs will take care of themselves.", "Dale Carnegie"),
    ("Motivation gets you going, but discipline keeps you growing.", "John C. Maxwell"),
    ("The way to get started is to quit talking and begin doing.", "Walt Disney"),
    ("Small daily improvements are the key to staggering long-term results.", "Robin Sharma"),
    ("You cannot escape the responsibility of tomorrow by evading it today.", "Abraham Lincoln"),
    ("Starve your distractions, feed your focus.", "Unknown"),
    ("Don't watch the clock; do what it does. Keep going.", "Sam Levenson"),
    ("The pain you feel today will be the strength you feel tomorrow.", "Unknown"),
    ("Success is the sum of small efforts repeated day in and day out.", "Robert Collier"),
]

MOMENT_PREFIX = {
    "morning": "Start strong",
    "focus_start": "Lock in",
    "break": "Rest well",
    "blocked": "Stay the course",
    "evening": "Wind down",
    "streak": "Keep it alive",
}

ENCOURAGE_PROMPT = (
    "Write ONE short (max 25 words) personalized encouragement for the user. "
    "Context: {context}. No emojis, no markdown, no quotes around it."
)


def get_random_quote() -> tuple[str, str]:
    """Return a random (quote, author) tuple."""
    return random.choice(QUOTES)


def get_quote_for_moment(moment: str) -> tuple[str, str]:
    """Return a quote picked with bias toward a moment prefix."""
    prefix = MOMENT_PREFIX.get(moment, "")
    if prefix:
        matching = [q for q in QUOTES if prefix.split()[0].lower() in q[0].lower()]
        if matching:
            return random.choice(matching)
    return get_random_quote()


async def generate_encouragement(api_key: str, context: dict) -> str:
    """LLM-generated personalized encouragement."""
    ctx_str = ", ".join(f"{k}={v}" for k, v in (context or {}).items()) or "general focus"
    result = await classifier.call_gemini(api_key, ENCOURAGE_PROMPT.format(context=ctx_str), max_tokens=80)
    return result.strip().strip('"').strip("'")


def daily_affirmation(conn) -> str:
    """Return today's affirmation, cached in config per day."""
    today = _dt.datetime.now().strftime("%Y-%m-%d")
    cached = db.get_config(conn, "motivation_affirmation_date")
    if cached == today:
        stored = db.get_config(conn, "motivation_affirmation_text")
        if stored:
            return stored
    quote, author = get_random_quote()
    text = f"{quote} — {author}"
    db.set_config(conn, "motivation_affirmation_date", today)
    db.set_config(conn, "motivation_affirmation_text", text)
    return text
