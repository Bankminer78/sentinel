"""Tests for sentinel.nlp_advanced."""
import pytest
from unittest.mock import patch, AsyncMock
from sentinel import nlp_advanced as nlp


def test_tokenize():
    tokens = nlp.tokenize("Hello world, this is a test!")
    assert tokens == ["hello", "world", "this", "is", "a", "test"]


def test_tokenize_empty():
    assert nlp.tokenize("") == []


def test_extract_keywords():
    text = "python python python programming code code"
    kws = nlp.extract_keywords(text)
    # 'python' should be top, but it's 6 chars > 3
    assert any(k["word"] == "python" for k in kws)


def test_extract_keywords_filters_stopwords():
    text = "the the the the important important"
    kws = nlp.extract_keywords(text)
    assert any(k["word"] == "important" for k in kws)
    assert not any(k["word"] == "the" for k in kws)


def test_extract_keywords_limit():
    text = " ".join(f"word{i}" for i in range(20))
    kws = nlp.extract_keywords(text, limit=5)
    assert len(kws) <= 5


def test_word_frequency():
    freq = nlp.word_frequency("a b c a b a")
    assert freq["a"] == 3
    assert freq["b"] == 2
    assert freq["c"] == 1


def test_sentence_split():
    text = "First sentence. Second sentence! Third?"
    sentences = nlp.sentence_split(text)
    assert len(sentences) == 3


def test_sentence_split_empty():
    assert nlp.sentence_split("") == []


def test_readability_score_simple():
    text = "This is a simple sentence."
    score = nlp.readability_score(text)
    assert score > 0


def test_readability_score_empty():
    assert nlp.readability_score("") == 0.0


def test_extract_topics():
    texts = ["python code", "python tutorial", "javascript code"]
    topics = nlp.extract_topics(texts)
    assert "python" in topics or "code" in topics


def test_extract_topics_empty():
    assert nlp.extract_topics([]) == []


def test_extract_domains_from_text():
    text = "Visit github.com and google.com for info"
    domains = nlp.extract_domains_from_text(text)
    assert "github.com" in domains
    assert "google.com" in domains


def test_extract_times_from_text():
    text = "Meet at 14:30 or 2:45 PM"
    times = nlp.extract_times_from_text(text)
    assert len(times) >= 1


@pytest.mark.asyncio
async def test_classify_sentiment_positive():
    with patch("sentinel.nlp_advanced.classifier.call_gemini",
               new_callable=AsyncMock, return_value="positive"):
        result = await nlp.classify_sentiment("I love this!", "key")
        assert result == "positive"


@pytest.mark.asyncio
async def test_classify_sentiment_invalid():
    with patch("sentinel.nlp_advanced.classifier.call_gemini",
               new_callable=AsyncMock, return_value="gibberish"):
        result = await nlp.classify_sentiment("neutral", "key")
        assert result == "neutral"


@pytest.mark.asyncio
async def test_classify_sentiment_error():
    with patch("sentinel.nlp_advanced.classifier.call_gemini",
               new_callable=AsyncMock, side_effect=Exception("fail")):
        result = await nlp.classify_sentiment("text", "key")
        assert result == "neutral"


def test_syllable_count():
    assert nlp._syllable_count("hello") >= 1
    assert nlp._syllable_count("test") >= 1
