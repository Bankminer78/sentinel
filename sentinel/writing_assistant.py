"""AI writing assistant — proofread, summarize, rewrite."""
from . import classifier


async def proofread(text: str, api_key: str) -> str:
    prompt = f"Proofread this text and return the corrected version only (no explanation):\n\n{text}"
    try:
        return await classifier.call_gemini(api_key, prompt, max_tokens=2000)
    except Exception:
        return text


async def summarize(text: str, api_key: str, max_sentences: int = 3) -> str:
    prompt = f"Summarize this text in at most {max_sentences} sentences:\n\n{text}"
    try:
        return await classifier.call_gemini(api_key, prompt, max_tokens=300)
    except Exception:
        return text[:200] + "..."


async def rewrite(text: str, api_key: str, style: str = "concise") -> str:
    prompt = f"Rewrite this text in a {style} style. Return only the rewritten version:\n\n{text}"
    try:
        return await classifier.call_gemini(api_key, prompt, max_tokens=2000)
    except Exception:
        return text


async def continue_writing(text: str, api_key: str) -> str:
    prompt = f"Continue this text naturally. Return only the continuation:\n\n{text}"
    try:
        return await classifier.call_gemini(api_key, prompt, max_tokens=500)
    except Exception:
        return ""


async def translate(text: str, api_key: str, target_language: str) -> str:
    prompt = f"Translate this to {target_language}. Return only the translation:\n\n{text}"
    try:
        return await classifier.call_gemini(api_key, prompt, max_tokens=2000)
    except Exception:
        return text


async def bullet_points(text: str, api_key: str) -> list:
    prompt = f"Extract the key points from this text as a bullet list (one per line, starting with -):\n\n{text}"
    try:
        result = await classifier.call_gemini(api_key, prompt, max_tokens=500)
        return [line.strip()[2:].strip() for line in result.splitlines()
                if line.strip().startswith("-")]
    except Exception:
        return []


async def explain_simply(text: str, api_key: str) -> str:
    prompt = f"Explain this like I'm 10 years old:\n\n{text}"
    try:
        return await classifier.call_gemini(api_key, prompt, max_tokens=500)
    except Exception:
        return text


async def check_tone(text: str, api_key: str) -> str:
    prompt = f"What is the tone of this text? Answer in one or two words:\n\n{text}"
    try:
        return await classifier.call_gemini(api_key, prompt, max_tokens=20)
    except Exception:
        return "neutral"


def count_words(text: str) -> int:
    return len([w for w in text.split() if w])


def reading_time_minutes(text: str, wpm: int = 200) -> float:
    return round(count_words(text) / wpm, 1)
