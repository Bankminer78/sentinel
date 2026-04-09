"""Tests for sentinel.nlp — natural language rule helpers."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from sentinel import nlp, classifier


class TestNormalizeRuleText:
    @pytest.mark.asyncio
    async def test_returns_string(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock,
                          return_value="Block YouTube"):
            r = await nlp.normalize_rule_text("k", "i wanna block youtube plz")
            assert r == "Block YouTube"

    @pytest.mark.asyncio
    async def test_empty_returns_empty(self):
        r = await nlp.normalize_rule_text("k", "")
        assert r == ""

    @pytest.mark.asyncio
    async def test_strips_quotes(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock,
                          return_value='"Block Reddit"'):
            r = await nlp.normalize_rule_text("k", "block reddit")
            assert r == "Block Reddit"


class TestSplitCompoundRule:
    @pytest.mark.asyncio
    async def test_splits_on_lines(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock,
                          return_value="Block YouTube\nBlock Reddit"):
            r = await nlp.split_compound_rule("k", "Block YouTube and Reddit")
            assert r == ["Block YouTube", "Block Reddit"]

    @pytest.mark.asyncio
    async def test_strips_bullets(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock,
                          return_value="- Block X\n- Block Y"):
            r = await nlp.split_compound_rule("k", "Block X and Y")
            assert r == ["Block X", "Block Y"]

    @pytest.mark.asyncio
    async def test_strips_numbering(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock,
                          return_value="1. Block A\n2. Block B"):
            r = await nlp.split_compound_rule("k", "both")
            assert r == ["Block A", "Block B"]

    @pytest.mark.asyncio
    async def test_empty_text_empty_list(self):
        r = await nlp.split_compound_rule("k", "")
        assert r == []

    @pytest.mark.asyncio
    async def test_single_rule(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock,
                          return_value="Block YouTube"):
            r = await nlp.split_compound_rule("k", "Block YouTube")
            assert r == ["Block YouTube"]


class TestExtractIntent:
    @pytest.mark.asyncio
    async def test_returns_dict(self):
        payload = json.dumps({"action": "block", "targets": ["youtube.com"],
                              "time": "work hours", "duration": 0})
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value=payload):
            r = await nlp.extract_intent("k", "block youtube at work")
            assert r["action"] == "block"
            assert r["targets"] == ["youtube.com"]

    @pytest.mark.asyncio
    async def test_limit_action(self):
        payload = json.dumps({"action": "limit", "targets": ["twitter.com"],
                              "time": "", "duration": 30})
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value=payload):
            r = await nlp.extract_intent("k", "limit twitter to 30 min")
            assert r["action"] == "limit"
            assert r["duration"] == 30

    @pytest.mark.asyncio
    async def test_invalid_action_defaults_block(self):
        payload = json.dumps({"action": "frobnicate", "targets": [], "time": "", "duration": 0})
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value=payload):
            r = await nlp.extract_intent("k", "x")
            assert r["action"] == "block"

    @pytest.mark.asyncio
    async def test_malformed_json_fallback(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock,
                          return_value="not json"):
            r = await nlp.extract_intent("k", "foo")
            assert r["action"] == "block"
            assert r["targets"] == []
            assert r["duration"] == 0

    @pytest.mark.asyncio
    async def test_markdown_fences_stripped(self):
        payload = json.dumps({"action": "allow", "targets": ["a"], "time": "", "duration": 0})
        fenced = f"```json\n{payload}\n```"
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value=fenced):
            r = await nlp.extract_intent("k", "x")
            assert r["action"] == "allow"


class TestSuggestBetterPhrasing:
    @pytest.mark.asyncio
    async def test_returns_suggestion(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock,
                          return_value="Block social media weekdays 9-5"):
            r = await nlp.suggest_better_phrasing("k", "no twitter while working")
            assert "Block" in r

    @pytest.mark.asyncio
    async def test_empty_returns_empty(self):
        r = await nlp.suggest_better_phrasing("k", "")
        assert r == ""


class TestDetectConflicts:
    def test_no_overlap_no_conflict(self):
        a = {"action": "block", "targets": ["youtube.com"]}
        b = {"action": "allow", "targets": ["reddit.com"]}
        assert nlp.detect_conflicts(a, b) is None

    def test_block_vs_allow_same_target(self):
        a = {"action": "block", "targets": ["youtube.com"]}
        b = {"action": "allow", "targets": ["youtube.com"]}
        assert nlp.detect_conflicts(a, b) is not None

    def test_same_action_no_conflict(self):
        a = {"action": "block", "targets": ["x.com"]}
        b = {"action": "block", "targets": ["x.com"]}
        assert nlp.detect_conflicts(a, b) is None

    def test_category_overlap_conflict(self):
        a = {"action": "block", "categories": ["social"]}
        b = {"action": "allow", "categories": ["social"]}
        assert nlp.detect_conflicts(a, b) is not None

    def test_missing_action_no_conflict(self):
        a = {"targets": ["x.com"]}
        b = {"targets": ["x.com"]}
        assert nlp.detect_conflicts(a, b) is None
