"""Tests for sentinel.writing_assistant."""
import pytest
from unittest.mock import patch, AsyncMock
from sentinel import writing_assistant as wa


@pytest.mark.asyncio
async def test_proofread():
    with patch("sentinel.writing_assistant.classifier.call_gemini",
               new_callable=AsyncMock, return_value="Corrected text"):
        result = await wa.proofread("Incorect text", "key")
        assert result == "Corrected text"


@pytest.mark.asyncio
async def test_proofread_error():
    with patch("sentinel.writing_assistant.classifier.call_gemini",
               new_callable=AsyncMock, side_effect=Exception("fail")):
        result = await wa.proofread("text", "key")
        assert result == "text"  # fallback


@pytest.mark.asyncio
async def test_summarize():
    with patch("sentinel.writing_assistant.classifier.call_gemini",
               new_callable=AsyncMock, return_value="Short summary"):
        result = await wa.summarize("Long text here", "key")
        assert result == "Short summary"


@pytest.mark.asyncio
async def test_rewrite():
    with patch("sentinel.writing_assistant.classifier.call_gemini",
               new_callable=AsyncMock, return_value="Rewritten"):
        result = await wa.rewrite("Original", "key", "formal")
        assert result == "Rewritten"


@pytest.mark.asyncio
async def test_continue_writing():
    with patch("sentinel.writing_assistant.classifier.call_gemini",
               new_callable=AsyncMock, return_value="continued..."):
        result = await wa.continue_writing("Once upon a time", "key")
        assert "continued" in result


@pytest.mark.asyncio
async def test_translate():
    with patch("sentinel.writing_assistant.classifier.call_gemini",
               new_callable=AsyncMock, return_value="Bonjour"):
        result = await wa.translate("Hello", "key", "French")
        assert result == "Bonjour"


@pytest.mark.asyncio
async def test_bullet_points():
    with patch("sentinel.writing_assistant.classifier.call_gemini",
               new_callable=AsyncMock, return_value="- Point 1\n- Point 2\n- Point 3"):
        points = await wa.bullet_points("Text", "key")
        assert len(points) == 3


@pytest.mark.asyncio
async def test_explain_simply():
    with patch("sentinel.writing_assistant.classifier.call_gemini",
               new_callable=AsyncMock, return_value="Simple explanation"):
        result = await wa.explain_simply("Complex topic", "key")
        assert result == "Simple explanation"


@pytest.mark.asyncio
async def test_check_tone():
    with patch("sentinel.writing_assistant.classifier.call_gemini",
               new_callable=AsyncMock, return_value="formal"):
        tone = await wa.check_tone("Dear Sir", "key")
        assert tone == "formal"


def test_count_words():
    assert wa.count_words("hello world") == 2
    assert wa.count_words("") == 0


def test_reading_time():
    text = " ".join(["word"] * 200)
    assert wa.reading_time_minutes(text) == 1.0
