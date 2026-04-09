"""Linear integration — sync with Linear issues (GraphQL)."""
import httpx
from . import db


LINEAR_URL = "https://api.linear.app/graphql"


def set_token(conn, token: str):
    db.set_config(conn, "linear_token", token)


def get_token(conn) -> str:
    return db.get_config(conn, "linear_token", "") or ""


def is_configured(conn) -> bool:
    return bool(get_token(conn))


def _headers(token: str) -> dict:
    return {"Authorization": token, "Content-Type": "application/json"}


async def _graphql(conn, query: str, variables: dict = None) -> dict:
    token = get_token(conn)
    if not token:
        return {}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(LINEAR_URL, headers=_headers(token),
                                  json={"query": query, "variables": variables or {}})
            return r.json()
    except Exception:
        return {}


async def get_issues(conn, state: str = None) -> list:
    query = """query { issues(first: 50) { nodes { id title description state { name } priority url } } }"""
    result = await _graphql(conn, query)
    issues = result.get("data", {}).get("issues", {}).get("nodes", [])
    if state:
        issues = [i for i in issues if i.get("state", {}).get("name") == state]
    return issues


async def get_my_issues(conn) -> list:
    query = """query { viewer { assignedIssues(first: 50) { nodes { id title state { name } url } } } }"""
    result = await _graphql(conn, query)
    return result.get("data", {}).get("viewer", {}).get("assignedIssues", {}).get("nodes", [])


async def create_issue(conn, title: str, description: str = "", team_id: str = None) -> dict:
    if not team_id:
        # Get first team
        teams_query = "query { teams(first: 1) { nodes { id } } }"
        teams_result = await _graphql(conn, teams_query)
        teams = teams_result.get("data", {}).get("teams", {}).get("nodes", [])
        if not teams:
            return {"error": "no teams"}
        team_id = teams[0]["id"]
    mutation = """mutation($title: String!, $desc: String!, $teamId: String!) {
        issueCreate(input: { title: $title, description: $desc, teamId: $teamId }) {
            success
            issue { id title url }
        }
    }"""
    variables = {"title": title, "desc": description, "teamId": team_id}
    result = await _graphql(conn, mutation, variables)
    return result.get("data", {}).get("issueCreate", {})


async def get_teams(conn) -> list:
    query = "query { teams { nodes { id name } } }"
    result = await _graphql(conn, query)
    return result.get("data", {}).get("teams", {}).get("nodes", [])


async def get_user(conn) -> dict:
    query = "query { viewer { id name email } }"
    result = await _graphql(conn, query)
    return result.get("data", {}).get("viewer", {})


def clear_config(conn):
    db.set_config(conn, "linear_token", "")


async def issue_count(conn) -> int:
    issues = await get_issues(conn)
    return len(issues)
