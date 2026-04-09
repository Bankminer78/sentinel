"""Tests for sentinel.sdk."""
import pytest
from unittest.mock import patch, MagicMock
from sentinel import sdk


def test_sentinel_init():
    s = sdk.Sentinel()
    assert s.base_url == "http://localhost:9849"


def test_sentinel_custom_url():
    s = sdk.Sentinel(base_url="http://custom:8080")
    assert s.base_url == "http://custom:8080"


def test_sentinel_with_api_key():
    s = sdk.Sentinel(api_key="test123")
    assert "Authorization" in s._headers


def test_sentinel_no_api_key():
    s = sdk.Sentinel()
    assert "Authorization" not in s._headers


def test_url_builder():
    s = sdk.Sentinel()
    assert s._url("/rules") == "http://localhost:9849/rules"


def test_get():
    s = sdk.Sentinel()
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": "test"}
    with patch("sentinel.sdk.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get = MagicMock(return_value=mock_response)
        result = s.get("/test")
        assert result == {"data": "test"}


def test_post():
    s = sdk.Sentinel()
    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": True}
    with patch("sentinel.sdk.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.post = MagicMock(return_value=mock_response)
        result = s.post("/rules", {"text": "test"})
        assert result == {"ok": True}


def test_delete():
    s = sdk.Sentinel()
    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": True}
    with patch("sentinel.sdk.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.delete = MagicMock(return_value=mock_response)
        result = s.delete("/rules/1")
        assert result == {"ok": True}


def test_add_rule():
    s = sdk.Sentinel()
    with patch.object(s, "post", return_value={"id": 1}):
        result = s.add_rule("Block YouTube")
        assert result == {"id": 1}


def test_list_rules():
    s = sdk.Sentinel()
    with patch.object(s, "get", return_value=[{"id": 1}]):
        assert len(s.list_rules()) == 1


def test_score():
    s = sdk.Sentinel()
    with patch.object(s, "get", return_value={"score": 85}):
        assert s.score() == 85


def test_client_singleton():
    c1 = sdk.client()
    c2 = sdk.client()
    assert c1 is c2


def test_client_different_url():
    c1 = sdk.client("http://a")
    c2 = sdk.client("http://b")
    assert c1 is not c2
