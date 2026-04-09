"""Tests for sentinel.query — natural language Q&A over data."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from sentinel import db, query


class _FakeGemini:
    def __init__(self, answer):
        self.answer = answer
        self.last_prompt = ""

    async def __call__(self, api_key, prompt, max_tokens=50):
        self.last_prompt = prompt
        return self.answer


class TestBuildContext:
    def test_context_has_keys(self, conn):
        ctx = query.build_context(conn)
        assert set(ctx.keys()) == {"activities", "rules", "config"}

    def test_context_empty_activities(self, conn):
        ctx = query.build_context(conn)
        assert ctx["activities"] == []

    def test_context_api_key_flag(self, conn):
        db.set_config(conn, "gemini_api_key", "KEY")
        ctx = query.build_context(conn)
        assert ctx["config"]["api_key_set"] is True


class TestAsk:
    def test_no_api_key(self, conn):
        result = asyncio.run(query.ask(conn, "hi", ""))
        assert "API key" in result

    def test_blank_question(self, conn):
        result = asyncio.run(query.ask(conn, "   ", "KEY"))
        assert "question" in result.lower()

    def test_includes_activities_in_prompt(self, conn):
        db.log_activity(conn, "Chrome", "YouTube", "https://youtube.com", "youtube.com", verdict="block")
        call = _FakeGemini("You spent 5 minutes on YouTube.")
        with patch("sentinel.classifier.call_gemini", new=call):
            answer = asyncio.run(query.ask(conn, "how much time on youtube?", "KEY"))
        assert "youtube.com" in call.last_prompt
        assert "5 minutes" in answer

    def test_includes_rules_in_prompt(self, conn):
        db.add_rule(conn, "Block YouTube during work")
        call = _FakeGemini("You have 1 rule.")
        with patch("sentinel.classifier.call_gemini", new=call):
            asyncio.run(query.ask(conn, "what rules?", "KEY"))
        assert "Block YouTube during work" in call.last_prompt

    def test_returns_gemini_answer(self, conn):
        call = _FakeGemini("42 minutes")
        with patch("sentinel.classifier.call_gemini", new=call):
            answer = asyncio.run(query.ask(conn, "how long?", "KEY"))
        assert answer == "42 minutes"

    def test_gemini_error_is_handled(self, conn):
        async def failing(api_key, prompt, max_tokens=50):
            raise RuntimeError("boom")
        with patch("sentinel.classifier.call_gemini", new=failing):
            answer = asyncio.run(query.ask(conn, "x", "KEY"))
        assert "Error" in answer

    def test_summarize_activities_empty(self):
        assert "no activities" in query._summarize_activities([])

    def test_summarize_rules_empty(self):
        assert "no rules" in query._summarize_rules([])
