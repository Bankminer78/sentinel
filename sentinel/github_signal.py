"""GitHub activity as productivity signal."""
import httpx, time
from datetime import datetime
from . import db


async def fetch_user_events(username: str, token: str = None, since_ts: float = None) -> list:
    """Fetch recent events for a user."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    url = f"https://api.github.com/users/{username}/events"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            events = r.json()
            if since_ts:
                events = [e for e in events if datetime.fromisoformat(
                    e["created_at"].replace("Z", "+00:00")).timestamp() >= since_ts]
            return events
    except Exception:
        return []


def score_events(events: list) -> dict:
    """Count events by type."""
    counts = {"commits": 0, "prs": 0, "reviews": 0, "issues": 0}
    for e in events:
        t = e.get("type", "")
        if t == "PushEvent":
            counts["commits"] += len(e.get("payload", {}).get("commits", []))
        elif t == "PullRequestEvent":
            counts["prs"] += 1
        elif t == "PullRequestReviewEvent":
            counts["reviews"] += 1
        elif t == "IssuesEvent":
            counts["issues"] += 1
    return counts


async def daily_github_score(conn, username: str, token: str = None) -> dict:
    """Today's GitHub activity score."""
    today_start = datetime.combine(datetime.now().date(), datetime.min.time()).timestamp()
    events = await fetch_user_events(username, token, since_ts=today_start)
    counts = score_events(events)
    score = counts["commits"] * 2 + counts["prs"] * 10 + counts["reviews"] * 5 + counts["issues"] * 3
    return {**counts, "score": score}


def set_github_config(conn, username: str, token: str = None):
    db.set_config(conn, "github_username", username)
    if token:
        db.set_config(conn, "github_token", token)


def get_github_config(conn) -> dict:
    return {
        "username": db.get_config(conn, "github_username"),
        "token": db.get_config(conn, "github_token"),
    }
