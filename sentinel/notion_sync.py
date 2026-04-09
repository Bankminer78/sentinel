"""Notion integration — sync rules/goals/habits to Notion databases."""
import httpx
from . import db


def set_config(conn, token: str, db_id: str):
    db.set_config(conn, "notion_token", token)
    db.set_config(conn, "notion_db_id", db_id)


def get_config(conn) -> dict:
    return {
        "token": db.get_config(conn, "notion_token"),
        "db_id": db.get_config(conn, "notion_db_id"),
    }


async def create_page(conn, title: str, content: str = "") -> dict:
    cfg = get_config(conn)
    if not cfg["token"] or not cfg["db_id"]:
        return {"error": "not configured"}
    headers = {
        "Authorization": f"Bearer {cfg['token']}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    payload = {
        "parent": {"database_id": cfg["db_id"]},
        "properties": {
            "Name": {"title": [{"text": {"content": title}}]}
        },
    }
    if content:
        payload["children"] = [{
            "object": "block",
            "paragraph": {"rich_text": [{"text": {"content": content}}]},
        }]
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://api.notion.com/v1/pages", json=payload, headers=headers)
            return r.json()
    except Exception as e:
        return {"error": str(e)}


async def query_database(conn, filter_obj: dict = None) -> list:
    cfg = get_config(conn)
    if not cfg["token"] or not cfg["db_id"]:
        return []
    headers = {
        "Authorization": f"Bearer {cfg['token']}",
        "Notion-Version": "2022-06-28",
    }
    body = {"filter": filter_obj} if filter_obj else {}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"https://api.notion.com/v1/databases/{cfg['db_id']}/query",
                json=body, headers=headers)
            data = r.json()
            return data.get("results", [])
    except Exception:
        return []


async def sync_rules_to_notion(conn) -> int:
    rules = db.get_rules(conn)
    count = 0
    for r in rules:
        result = await create_page(conn, f"Rule: {r['text']}")
        if "error" not in result:
            count += 1
    return count


def is_configured(conn) -> bool:
    cfg = get_config(conn)
    return bool(cfg["token"] and cfg["db_id"])


def disable(conn):
    db.set_config(conn, "notion_token", "")
    db.set_config(conn, "notion_db_id", "")
