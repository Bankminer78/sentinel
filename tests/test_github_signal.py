"""Tests for sentinel.github_signal."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sentinel import github_signal, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_score_events_empty():
    assert github_signal.score_events([]) == {"commits": 0, "prs": 0, "reviews": 0, "issues": 0}


def test_score_push_event():
    events = [{"type": "PushEvent", "payload": {"commits": [{}, {}, {}]}}]
    assert github_signal.score_events(events)["commits"] == 3


def test_score_pr_event():
    events = [{"type": "PullRequestEvent"}, {"type": "PullRequestEvent"}]
    assert github_signal.score_events(events)["prs"] == 2


def test_score_review_event():
    events = [{"type": "PullRequestReviewEvent"}]
    assert github_signal.score_events(events)["reviews"] == 1


def test_score_issues_event():
    events = [{"type": "IssuesEvent"}]
    assert github_signal.score_events(events)["issues"] == 1


def test_score_mixed():
    events = [
        {"type": "PushEvent", "payload": {"commits": [{}]}},
        {"type": "PullRequestEvent"},
        {"type": "WatchEvent"},  # Unknown type
    ]
    r = github_signal.score_events(events)
    assert r["commits"] == 1
    assert r["prs"] == 1


@pytest.mark.asyncio
async def test_fetch_user_events_mock():
    mock_response = MagicMock()
    mock_response.json.return_value = [{"type": "PushEvent", "created_at": "2026-04-09T12:00:00Z", "payload": {"commits": []}}]
    mock_response.raise_for_status = MagicMock()
    with patch("sentinel.github_signal.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        events = await github_signal.fetch_user_events("alice")
        assert len(events) == 1


@pytest.mark.asyncio
async def test_fetch_user_events_error():
    with patch("sentinel.github_signal.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=Exception("network"))
        events = await github_signal.fetch_user_events("alice")
        assert events == []


def test_set_get_config(conn):
    github_signal.set_github_config(conn, "alice", "token123")
    cfg = github_signal.get_github_config(conn)
    assert cfg["username"] == "alice"
    assert cfg["token"] == "token123"


def test_config_without_token(conn):
    github_signal.set_github_config(conn, "alice")
    cfg = github_signal.get_github_config(conn)
    assert cfg["username"] == "alice"


@pytest.mark.asyncio
async def test_daily_score_mock(conn):
    with patch("sentinel.github_signal.fetch_user_events", new_callable=AsyncMock,
               return_value=[{"type": "PushEvent", "payload": {"commits": [{}, {}]}}]):
        score = await github_signal.daily_github_score(conn, "alice")
        assert score["commits"] == 2
        assert score["score"] == 4  # 2 commits * 2


def test_score_formula():
    events = [
        {"type": "PushEvent", "payload": {"commits": [{}, {}]}},  # 2 commits
        {"type": "PullRequestEvent"},  # 1 PR
    ]
    r = github_signal.score_events(events)
    # commits: 2*2=4, prs: 1*10=10, total=14
    assert r["commits"] == 2
    assert r["prs"] == 1
