"""Tests for sentinel.screenshots — vision capture + analysis."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel import screenshots


# The background-monitor module-level state was removed in Phase 5; nothing
# to reset between tests now.


class TestTakeScreenshot:
    def test_success_returns_true(self):
        with patch("sentinel.screenshots.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert screenshots.take_screenshot("/tmp/x.png") is True

    def test_failure_returns_false(self):
        with patch("sentinel.screenshots.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert screenshots.take_screenshot("/tmp/x.png") is False

    def test_subprocess_error_returns_false(self):
        import subprocess as sp
        with patch("sentinel.screenshots.subprocess.run", side_effect=sp.SubprocessError()):
            assert screenshots.take_screenshot() is False

    def test_file_not_found_returns_false(self):
        with patch("sentinel.screenshots.subprocess.run", side_effect=FileNotFoundError()):
            assert screenshots.take_screenshot() is False


class TestAnalyzeScreenshot:
    @pytest.mark.asyncio
    async def test_missing_file_returns_empty(self, tmp_path):
        result = await screenshots.analyze_screenshot(str(tmp_path / "nope.png"), "k", "p")
        assert result == ""

    @pytest.mark.asyncio
    async def test_posts_to_gemini(self, tmp_path):
        p = tmp_path / "img.png"
        p.write_bytes(b"fake-image-bytes")
        with patch("sentinel.screenshots.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": '{"verdict":"productive","details":"coding"}'}]}}]
            }
            mock_client.post = AsyncMock(return_value=mock_resp)
            result = await screenshots.analyze_screenshot(str(p), "key", "prompt")
            assert "productive" in result


class TestParseVerdict:
    def test_valid_json(self):
        r = screenshots._parse_verdict('{"verdict":"productive","details":"coding"}')
        assert r["verdict"] == "productive"
        assert r["details"] == "coding"

    def test_distracted(self):
        r = screenshots._parse_verdict('{"verdict":"distracted","details":"scrolling"}')
        assert r["verdict"] == "distracted"

    def test_invalid_verdict_normalized(self):
        r = screenshots._parse_verdict('{"verdict":"wrong","details":"x"}')
        assert r["verdict"] == "neutral"

    def test_markdown_fences_stripped(self):
        r = screenshots._parse_verdict('```json\n{"verdict":"productive","details":"x"}\n```')
        assert r["verdict"] == "productive"

    def test_malformed_json_fallback(self):
        r = screenshots._parse_verdict("not json at all")
        assert r["verdict"] == "neutral"


class TestCaptureAndAnalyze:
    @pytest.mark.asyncio
    async def test_capture_fails_returns_neutral(self):
        with patch("sentinel.screenshots.take_screenshot", return_value=False):
            r = await screenshots.capture_and_analyze("key")
            assert r["verdict"] == "neutral"

    @pytest.mark.asyncio
    async def test_happy_path(self):
        with patch("sentinel.screenshots.take_screenshot", return_value=True), \
             patch("sentinel.screenshots.analyze_screenshot",
                   new=AsyncMock(return_value='{"verdict":"productive","details":"vim"}')):
            r = await screenshots.capture_and_analyze("key", "coding")
            assert r["verdict"] == "productive"
            assert "vim" in r["details"]

    @pytest.mark.asyncio
    async def test_empty_response_neutral(self):
        with patch("sentinel.screenshots.take_screenshot", return_value=True), \
             patch("sentinel.screenshots.analyze_screenshot", new=AsyncMock(return_value="")):
            r = await screenshots.capture_and_analyze("key")
            assert r["verdict"] == "neutral"
