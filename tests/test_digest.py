"""Tests for sentinel.digest — daily/weekly digest generation."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from sentinel import db, digest


@pytest.mark.asyncio
class TestDailyDigest:
    async def test_success(self, conn):
        with patch("sentinel.digest.classifier.call_gemini",
                   new=AsyncMock(return_value="Great day!")):
            out = await digest.generate_daily_digest(conn, "k")
        assert out == "Great day!"

    async def test_fallback_on_error(self, conn):
        with patch("sentinel.digest.classifier.call_gemini",
                   new=AsyncMock(side_effect=Exception("boom"))):
            out = await digest.generate_daily_digest(conn, "k")
        assert "score" in out.lower()


@pytest.mark.asyncio
class TestWeeklyDigest:
    async def test_success(self, conn):
        with patch("sentinel.digest.classifier.call_gemini",
                   new=AsyncMock(return_value="Solid week.")):
            out = await digest.generate_weekly_digest(conn, "k")
        assert out == "Solid week."

    async def test_fallback(self, conn):
        with patch("sentinel.digest.classifier.call_gemini",
                   new=AsyncMock(side_effect=Exception("boom"))):
            out = await digest.generate_weekly_digest(conn, "k")
        assert "weekly" in out.lower() or "score" in out.lower()


class TestFormatters:
    def test_html_contains_text(self):
        out = digest.format_digest_html("hello world", {"score": 77})
        assert "hello world" in out
        assert "77" in out
        assert "<html>" in out

    def test_html_dark_theme(self):
        out = digest.format_digest_html("x", {"score": 1})
        assert "#18181b" in out
        assert "#ef4444" in out

    def test_markdown_contains_text(self):
        out = digest.format_digest_markdown("hey", {"score": 42})
        assert "# Sentinel Digest" in out
        assert "hey" in out
        assert "42" in out

    def test_markdown_has_json_block(self):
        out = digest.format_digest_markdown("hi", {"score": 10, "x": 1})
        assert "```json" in out

    def test_html_handles_missing_score(self):
        out = digest.format_digest_html("t", {"week": {"avg_score": 55}})
        assert "55" in out


@pytest.mark.asyncio
class TestSendDigest:
    async def test_sends_to_channels(self, conn):
        with patch("sentinel.digest.classifier.call_gemini",
                   new=AsyncMock(return_value="text")), \
             patch("sentinel.digest.notifications.send_all",
                   new=AsyncMock(return_value={"macos": True})) as send:
            out = await digest.send_digest(conn, "k", channels=["macos"])
        assert out == {"macos": True}
        send.assert_called_once()

    async def test_default_channels(self, conn):
        with patch("sentinel.digest.classifier.call_gemini",
                   new=AsyncMock(return_value="text")), \
             patch("sentinel.digest.notifications.send_all",
                   new=AsyncMock(return_value={"macos": True})):
            out = await digest.send_digest(conn, "k")
        assert "macos" in out
