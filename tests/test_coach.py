"""Tests for sentinel.coach — AI productivity coach."""
import json
from unittest.mock import AsyncMock, patch
import pytest

from sentinel import coach


class TestMorningBriefing:
    @pytest.mark.asyncio
    async def test_returns_string(self, conn):
        with patch("sentinel.coach.classifier.call_gemini",
                   new_callable=AsyncMock, return_value="Good morning! Focus on deep work."):
            r = await coach.morning_briefing(conn, "fake-key")
            assert "Good morning" in r

    @pytest.mark.asyncio
    async def test_uses_stats(self, conn):
        mock = AsyncMock(return_value="briefing")
        with patch("sentinel.coach.classifier.call_gemini", mock):
            await coach.morning_briefing(conn, "fake-key")
            prompt = mock.call_args[0][1]
            assert "productive" in prompt


class TestEveningReflection:
    @pytest.mark.asyncio
    async def test_returns_string(self, conn):
        with patch("sentinel.coach.classifier.call_gemini",
                   new_callable=AsyncMock, return_value="Great day."):
            r = await coach.evening_reflection(conn, "fake-key")
            assert r == "Great day."

    @pytest.mark.asyncio
    async def test_calls_llm(self, conn):
        mock = AsyncMock(return_value="reflection")
        with patch("sentinel.coach.classifier.call_gemini", mock):
            await coach.evening_reflection(conn, "fake-key")
            assert mock.call_count == 1


class TestMidDayCheckIn:
    @pytest.mark.asyncio
    async def test_returns_string(self, conn):
        with patch("sentinel.coach.classifier.call_gemini",
                   new_callable=AsyncMock, return_value="Keep going."):
            r = await coach.mid_day_check_in(conn, "fake-key")
            assert "Keep" in r


class TestPatternAnalysis:
    @pytest.mark.asyncio
    async def test_returns_dict(self, conn):
        resp = json.dumps({"patterns": ["p1"], "insights": ["i1"], "recommendations": ["r1"]})
        with patch("sentinel.coach.classifier.call_gemini",
                   new_callable=AsyncMock, return_value=resp):
            r = await coach.pattern_analysis(conn, "fake-key", days=7)
            assert r["patterns"] == ["p1"]
            assert r["insights"] == ["i1"]

    @pytest.mark.asyncio
    async def test_malformed_fallback(self, conn):
        with patch("sentinel.coach.classifier.call_gemini",
                   new_callable=AsyncMock, return_value="not json"):
            r = await coach.pattern_analysis(conn, "fake-key")
            assert r == {"patterns": [], "insights": [], "recommendations": []}

    @pytest.mark.asyncio
    async def test_strips_markdown(self, conn):
        resp = "```json\n" + json.dumps({"patterns": [], "insights": [], "recommendations": ["rec"]}) + "\n```"
        with patch("sentinel.coach.classifier.call_gemini",
                   new_callable=AsyncMock, return_value=resp):
            r = await coach.pattern_analysis(conn, "fake-key")
            assert r["recommendations"] == ["rec"]


class TestPersonalizedNudge:
    @pytest.mark.asyncio
    async def test_returns_string(self, conn):
        with patch("sentinel.coach.classifier.call_gemini",
                   new_callable=AsyncMock, return_value="Refocus!"):
            r = await coach.personalized_nudge(conn, "fake-key",
                                               {"app": "Chrome", "domain": "twitter.com", "title": "X"})
            assert r == "Refocus!"

    @pytest.mark.asyncio
    async def test_uses_activity_in_prompt(self, conn):
        mock = AsyncMock(return_value="nudge")
        with patch("sentinel.coach.classifier.call_gemini", mock):
            await coach.personalized_nudge(conn, "fake-key",
                                           {"app": "Chrome", "domain": "twitter.com", "title": "T"})
            assert "twitter.com" in mock.call_args[0][1]

    @pytest.mark.asyncio
    async def test_handles_missing_fields(self, conn):
        with patch("sentinel.coach.classifier.call_gemini",
                   new_callable=AsyncMock, return_value="ok"):
            r = await coach.personalized_nudge(conn, "fake-key", {})
            assert r == "ok"


class TestWeeklyReview:
    @pytest.mark.asyncio
    async def test_returns_dict(self, conn):
        resp = json.dumps({"wins": ["w"], "challenges": ["c"], "focus": "deep work"})
        with patch("sentinel.coach.classifier.call_gemini",
                   new_callable=AsyncMock, return_value=resp):
            r = await coach.weekly_review(conn, "fake-key")
            assert r["wins"] == ["w"]
            assert r["focus"] == "deep work"

    @pytest.mark.asyncio
    async def test_malformed_fallback(self, conn):
        with patch("sentinel.coach.classifier.call_gemini",
                   new_callable=AsyncMock, return_value="bad"):
            r = await coach.weekly_review(conn, "fake-key")
            assert r == {"wins": [], "challenges": [], "focus": ""}
