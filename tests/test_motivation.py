"""Tests for sentinel.motivation — quotes, affirmations, encouragement."""

from unittest.mock import AsyncMock, patch

import pytest

from sentinel import motivation, classifier


class TestGetRandomQuote:
    def test_returns_tuple(self):
        q = motivation.get_random_quote()
        assert isinstance(q, tuple)
        assert len(q) == 2

    def test_quote_is_string(self):
        quote, author = motivation.get_random_quote()
        assert isinstance(quote, str)
        assert isinstance(author, str)
        assert quote

    def test_quotes_list_has_many(self):
        assert len(motivation.QUOTES) >= 20


class TestGetQuoteForMoment:
    def test_morning(self):
        q, a = motivation.get_quote_for_moment("morning")
        assert isinstance(q, str)
        assert q

    def test_focus_start(self):
        q, a = motivation.get_quote_for_moment("focus_start")
        assert q

    def test_break(self):
        q, a = motivation.get_quote_for_moment("break")
        assert q

    def test_blocked(self):
        q, a = motivation.get_quote_for_moment("blocked")
        assert q

    def test_evening(self):
        q, a = motivation.get_quote_for_moment("evening")
        assert q

    def test_streak(self):
        q, a = motivation.get_quote_for_moment("streak")
        assert q

    def test_unknown_moment_falls_back(self):
        q, a = motivation.get_quote_for_moment("nonsense")
        assert q


class TestGenerateEncouragement:
    @pytest.mark.asyncio
    async def test_returns_string(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock,
                          return_value="You've got this, keep going."):
            r = await motivation.generate_encouragement("k", {"goal": "deep work"})
            assert "got this" in r

    @pytest.mark.asyncio
    async def test_empty_context(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock,
                          return_value="Focus matters."):
            r = await motivation.generate_encouragement("k", {})
            assert r == "Focus matters."

    @pytest.mark.asyncio
    async def test_strips_quotes(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock,
                          return_value='"Keep going"'):
            r = await motivation.generate_encouragement("k", {"x": 1})
            assert r == "Keep going"


class TestDailyAffirmation:
    def test_returns_string(self, conn):
        r = motivation.daily_affirmation(conn)
        assert isinstance(r, str)
        assert r

    def test_cached_same_day(self, conn):
        r1 = motivation.daily_affirmation(conn)
        r2 = motivation.daily_affirmation(conn)
        assert r1 == r2

    def test_has_author_separator(self, conn):
        r = motivation.daily_affirmation(conn)
        assert " — " in r
