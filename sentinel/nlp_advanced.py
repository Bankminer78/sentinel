"""Advanced NLP — keyword extraction, readability, simple sentiment."""
from collections import Counter
import re
from . import classifier

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for",
    "of", "and", "or", "but", "with", "by", "from", "i", "you", "he", "she", "it",
    "we", "they", "this", "that", "these", "those", "my", "your", "his", "her",
    "be", "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "must", "can", "shall",
}


def tokenize(text: str) -> list:
    return re.findall(r"\b[a-zA-Z]+\b", text.lower())


def extract_keywords(text: str, limit: int = 10) -> list:
    tokens = [t for t in tokenize(text) if t not in STOPWORDS and len(t) > 3]
    counts = Counter(tokens)
    return [{"word": w, "count": c} for w, c in counts.most_common(limit)]


def extract_topics(texts: list, n_topics: int = 5) -> list:
    """Very simple topic extraction via word frequency across texts."""
    all_keywords = Counter()
    for text in texts:
        for kw in extract_keywords(text, limit=20):
            all_keywords[kw["word"]] += kw["count"]
    return [w for w, _ in all_keywords.most_common(n_topics)]


def word_frequency(text: str) -> dict:
    return dict(Counter(tokenize(text)))


def sentence_split(text: str) -> list:
    return [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]


def _syllable_count(word: str) -> int:
    word = word.lower()
    count = 0
    vowels = "aeiouy"
    if word and word[0] in vowels:
        count += 1
    for i in range(1, len(word)):
        if word[i] in vowels and word[i - 1] not in vowels:
            count += 1
    if word.endswith("e"):
        count -= 1
    return max(1, count)


def readability_score(text: str) -> float:
    """Flesch-Kincaid Reading Ease."""
    sentences = sentence_split(text)
    words = tokenize(text)
    if not sentences or not words:
        return 0.0
    syllables = sum(_syllable_count(w) for w in words)
    asl = len(words) / len(sentences)
    asw = syllables / len(words)
    return round(206.835 - 1.015 * asl - 84.6 * asw, 1)


async def classify_sentiment(text: str, api_key: str) -> str:
    prompt = f"Classify the sentiment of this text as 'positive', 'negative', or 'neutral'. Respond with only the word.\n\nText: {text}"
    try:
        result = await classifier.call_gemini(api_key, prompt, max_tokens=10)
        result = result.lower().strip()
        if result in ("positive", "negative", "neutral"):
            return result
    except Exception:
        pass
    return "neutral"


def extract_domains_from_text(text: str) -> list:
    return re.findall(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b", text)


def extract_times_from_text(text: str) -> list:
    return re.findall(r"\b\d{1,2}:\d{2}(?:\s*(?:am|pm|AM|PM))?\b", text)
