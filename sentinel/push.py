"""Push notifications via ntfy.sh, Pushover, Telegram."""
import httpx
from . import db


async def send_ntfy(topic: str, title: str, message: str, priority: int = 3) -> bool:
    """ntfy.sh — free, self-hostable push."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"https://ntfy.sh/{topic}",
                content=message.encode("utf-8"),
                headers={"Title": title, "Priority": str(priority)})
            return r.status_code < 300
    except Exception:
        return False


async def send_pushover(api_key: str, user_key: str, title: str, message: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                "https://api.pushover.net/1/messages.json",
                data={"token": api_key, "user": user_key, "title": title, "message": message})
            return r.status_code == 200
    except Exception:
        return False


async def send_telegram(bot_token: str, chat_id: str, message: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": message})
            return r.status_code == 200
    except Exception:
        return False


def configure_ntfy(conn, topic: str):
    db.set_config(conn, "ntfy_topic", topic)


def configure_pushover(conn, api_key: str, user_key: str):
    db.set_config(conn, "pushover_api_key", api_key)
    db.set_config(conn, "pushover_user_key", user_key)


def configure_telegram(conn, bot_token: str, chat_id: str):
    db.set_config(conn, "telegram_bot_token", bot_token)
    db.set_config(conn, "telegram_chat_id", chat_id)


async def send_all_push(conn, title: str, message: str) -> dict:
    """Send via all configured push services."""
    results = {}
    topic = db.get_config(conn, "ntfy_topic")
    if topic:
        results["ntfy"] = await send_ntfy(topic, title, message)
    po_api = db.get_config(conn, "pushover_api_key")
    po_user = db.get_config(conn, "pushover_user_key")
    if po_api and po_user:
        results["pushover"] = await send_pushover(po_api, po_user, title, message)
    tg_bot = db.get_config(conn, "telegram_bot_token")
    tg_chat = db.get_config(conn, "telegram_chat_id")
    if tg_bot and tg_chat:
        results["telegram"] = await send_telegram(tg_bot, tg_chat, f"{title}\n{message}")
    return results
