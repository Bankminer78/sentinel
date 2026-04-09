"""Todoist integration — sync tasks."""
import httpx
from . import db


BASE_URL = "https://api.todoist.com/rest/v2"


def set_token(conn, token: str):
    db.set_config(conn, "todoist_token", token)


def get_token(conn) -> str:
    return db.get_config(conn, "todoist_token", "") or ""


def is_configured(conn) -> bool:
    return bool(get_token(conn))


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def get_tasks(conn, project_id: str = None) -> list:
    token = get_token(conn)
    if not token:
        return []
    params = {}
    if project_id:
        params["project_id"] = project_id
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{BASE_URL}/tasks", headers=_headers(token), params=params)
            return r.json() if r.status_code == 200 else []
    except Exception:
        return []


async def create_task(conn, content: str, project_id: str = None, due: str = None) -> dict:
    token = get_token(conn)
    if not token:
        return {"error": "not configured"}
    payload = {"content": content}
    if project_id:
        payload["project_id"] = project_id
    if due:
        payload["due_string"] = due
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{BASE_URL}/tasks", headers=_headers(token), json=payload)
            return r.json() if r.status_code < 300 else {"error": f"status {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}


async def close_task(conn, task_id: str) -> bool:
    token = get_token(conn)
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{BASE_URL}/tasks/{task_id}/close", headers=_headers(token))
            return r.status_code == 204
    except Exception:
        return False


async def get_projects(conn) -> list:
    token = get_token(conn)
    if not token:
        return []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{BASE_URL}/projects", headers=_headers(token))
            return r.json() if r.status_code == 200 else []
    except Exception:
        return []


async def delete_task(conn, task_id: str) -> bool:
    token = get_token(conn)
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.delete(f"{BASE_URL}/tasks/{task_id}", headers=_headers(token))
            return r.status_code == 204
    except Exception:
        return False


def clear_config(conn):
    db.set_config(conn, "todoist_token", "")
