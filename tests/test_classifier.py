"""Tests for sentinel.classifier — LLM-based classification (async functional API)."""

import json
import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from sentinel import classifier


# ---------------------------------------------------------------------------
# Helper: patch call_gemini
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# call_gemini
# ---------------------------------------------------------------------------


class TestCallGemini:
    """Tests for the raw Gemini API call."""

    @pytest.mark.asyncio
    async def test_call_gemini_returns_string(self):
        with patch("sentinel.classifier.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": "social"}]}}]
            }
            mock_client.post = AsyncMock(return_value=mock_resp)
            result = await classifier.call_gemini("fake-key", "test prompt")
            assert result == "social"

    @pytest.mark.asyncio
    async def test_call_gemini_strips_whitespace(self):
        with patch("sentinel.classifier.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": "  social  \n"}]}}]
            }
            mock_client.post = AsyncMock(return_value=mock_resp)
            result = await classifier.call_gemini("fake-key", "test")
            assert result == "social"


# ---------------------------------------------------------------------------
# classify_domain
# ---------------------------------------------------------------------------


class TestClassifyDomain:
    """Tests for domain classification."""

    @pytest.mark.asyncio
    async def test_returns_valid_category(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="social"):
            result = await classifier.classify_domain("fake-key", "twitter.com")
            assert result == "social"

    @pytest.mark.asyncio
    async def test_returns_streaming(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="streaming"):
            result = await classifier.classify_domain("fake-key", "netflix.com")
            assert result == "streaming"

    @pytest.mark.asyncio
    async def test_returns_adult(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="adult"):
            result = await classifier.classify_domain("fake-key", "adult-site.com")
            assert result == "adult"

    @pytest.mark.asyncio
    async def test_returns_gaming(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="gaming"):
            result = await classifier.classify_domain("fake-key", "steam.com")
            assert result == "gaming"

    @pytest.mark.asyncio
    async def test_returns_shopping(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="shopping"):
            result = await classifier.classify_domain("fake-key", "wish.com")
            assert result == "shopping"

    @pytest.mark.asyncio
    async def test_returns_none_for_safe(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="none"):
            result = await classifier.classify_domain("fake-key", "github.com")
            assert result == "none"

    @pytest.mark.asyncio
    async def test_invalid_category_defaults_to_none(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="garbage"):
            result = await classifier.classify_domain("fake-key", "unknown.com")
            assert result == "none"

    @pytest.mark.asyncio
    async def test_caches_result(self):
        mock_gemini = AsyncMock(return_value="social")
        with patch.object(classifier, "call_gemini", mock_gemini):
            await classifier.classify_domain("fake-key", "twitter.com")
            await classifier.classify_domain("fake-key", "twitter.com")
            assert mock_gemini.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_expires(self):
        mock_gemini = AsyncMock(return_value="social")
        with patch.object(classifier, "call_gemini", mock_gemini):
            await classifier.classify_domain("fake-key", "twitter.com")
            # Manually expire the cache
            classifier._cache["twitter.com"] = ("social", time.time() - 7200)
            await classifier.classify_domain("fake-key", "twitter.com")
            assert mock_gemini.call_count == 2

    @pytest.mark.asyncio
    async def test_different_domains_not_cached_together(self):
        mock_gemini = AsyncMock(side_effect=["social", "streaming"])
        with patch.object(classifier, "call_gemini", mock_gemini):
            r1 = await classifier.classify_domain("fake-key", "twitter.com")
            r2 = await classifier.classify_domain("fake-key", "netflix.com")
            assert r1 == "social"
            assert r2 == "streaming"
            assert mock_gemini.call_count == 2

    @pytest.mark.asyncio
    async def test_normalizes_to_lowercase(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="Social"):
            result = await classifier.classify_domain("fake-key", "twitter.com")
            assert result == "social"


# ---------------------------------------------------------------------------
# parse_rule
# ---------------------------------------------------------------------------


class TestParseRule:
    """Tests for natural language to JSON rule parsing."""

    @pytest.mark.asyncio
    async def test_returns_dict(self):
        rule_json = json.dumps({"domains": ["youtube.com"], "action": "block"})
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value=rule_json):
            result = await classifier.parse_rule("fake-key", "Block YouTube")
            assert isinstance(result, dict)
            assert result["domains"] == ["youtube.com"]
            assert result["action"] == "block"

    @pytest.mark.asyncio
    async def test_strips_markdown_fences(self):
        rule_json = json.dumps({"domains": ["twitter.com"], "action": "block"})
        fenced = f"```json\n{rule_json}\n```"
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value=fenced):
            result = await classifier.parse_rule("fake-key", "Block Twitter")
            assert result["domains"] == ["twitter.com"]

    @pytest.mark.asyncio
    async def test_malformed_json_returns_fallback(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="not valid json"):
            result = await classifier.parse_rule("fake-key", "Block stuff")
            assert isinstance(result, dict)
            assert "categories" in result
            assert result["action"] == "block"

    @pytest.mark.asyncio
    async def test_schedule_field_parsed(self):
        rule_json = json.dumps({
            "domains": ["reddit.com"],
            "schedule": {"days": "mon-fri", "start": "09:00", "end": "17:00"},
            "action": "block",
        })
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value=rule_json):
            result = await classifier.parse_rule("fake-key", "Block Reddit 9-5 weekdays")
            assert "schedule" in result

    @pytest.mark.asyncio
    async def test_categories_field_parsed(self):
        rule_json = json.dumps({
            "categories": ["social", "streaming"],
            "action": "block",
        })
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value=rule_json):
            result = await classifier.parse_rule("fake-key", "Block social media and streaming")
            assert "social" in result["categories"]
            assert "streaming" in result["categories"]

    @pytest.mark.asyncio
    async def test_allowed_minutes_parsed(self):
        rule_json = json.dumps({
            "domains": ["youtube.com"],
            "allowed_minutes": 30,
            "action": "warn",
        })
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value=rule_json):
            result = await classifier.parse_rule("fake-key", "Allow 30 min of YouTube then warn")
            assert result["allowed_minutes"] == 30

    @pytest.mark.asyncio
    async def test_uses_higher_max_tokens(self):
        rule_json = json.dumps({"domains": ["test.com"], "action": "block"})
        mock_gemini = AsyncMock(return_value=rule_json)
        with patch.object(classifier, "call_gemini", mock_gemini):
            await classifier.parse_rule("fake-key", "Block test")
            _, kwargs = mock_gemini.call_args
            assert kwargs.get("max_tokens", 300) == 300


# ---------------------------------------------------------------------------
# evaluate_rules
# ---------------------------------------------------------------------------


class TestEvaluateRules:
    """Tests for rule evaluation."""

    @pytest.mark.asyncio
    async def test_returns_block(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="block"):
            result = await classifier.evaluate_rules(
                "fake-key", "Safari", "twitter.com", "Twitter", [{"text": "Block social", "parsed": "{}"}])
            assert result == "block"

    @pytest.mark.asyncio
    async def test_returns_warn(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="warn"):
            result = await classifier.evaluate_rules(
                "fake-key", "Chrome", "youtube.com", "YouTube", [{"text": "Warn streaming", "parsed": "{}"}])
            assert result == "warn"

    @pytest.mark.asyncio
    async def test_returns_allow(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="allow"):
            result = await classifier.evaluate_rules(
                "fake-key", "VS Code", "github.com", "GitHub", [{"text": "Block social", "parsed": "{}"}])
            assert result == "allow"

    @pytest.mark.asyncio
    async def test_invalid_verdict_defaults_to_allow(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="I think maybe block"):
            result = await classifier.evaluate_rules(
                "fake-key", "Safari", "twitter.com", "Twitter", [{"text": "Block social", "parsed": "{}"}])
            assert result == "allow"

    @pytest.mark.asyncio
    async def test_normalizes_to_lowercase(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="BLOCK"):
            result = await classifier.evaluate_rules(
                "fake-key", "Safari", "twitter.com", "Twitter", [{"text": "Block social", "parsed": "{}"}])
            assert result == "block"

    @pytest.mark.asyncio
    async def test_empty_rules_list(self):
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="allow"):
            result = await classifier.evaluate_rules(
                "fake-key", "Safari", "twitter.com", "Twitter", [])
            assert result == "allow"

    @pytest.mark.asyncio
    async def test_multiple_rules_in_prompt(self):
        mock_gemini = AsyncMock(return_value="block")
        rules = [
            {"text": "Block social media", "parsed": '{"categories": ["social"]}'},
            {"text": "Block streaming", "parsed": '{"categories": ["streaming"]}'},
        ]
        with patch.object(classifier, "call_gemini", mock_gemini):
            await classifier.evaluate_rules("fake-key", "Chrome", "twitter.com", "Twitter", rules)
            call_args = mock_gemini.call_args
            prompt = call_args[0][1]
            assert "Block social media" in prompt
            assert "Block streaming" in prompt
