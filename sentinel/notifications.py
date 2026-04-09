"""Notifications — macOS native + webhooks."""
import subprocess, httpx, asyncio, json
from . import db


def notify_macos(title: str, message: str, subtitle: str = "") -> bool:
    """Show macOS notification via osascript."""
    try:
        script = f'display notification "{message}" with title "{title}"'
        if subtitle:
            script += f' subtitle "{subtitle}"'
        subprocess.run(["osascript", "-e", script], timeout=5, check=False)
        return True
    except Exception:
        return False


def notify_sound(sound: str = "Glass") -> bool:
    """Play macOS sound."""
    try:
        subprocess.run(["afplay", f"/System/Library/Sounds/{sound}.aiff"], timeout=5, check=False)
        return True
    except Exception:
        return False


async def notify_webhook(url: str, payload: dict) -> bool:
    """POST to a webhook URL."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json=payload)
            return r.status_code < 300
    except Exception:
        return False


async def notify_slack(webhook_url: str, text: str) -> bool:
    """Send to Slack incoming webhook."""
    return await notify_webhook(webhook_url, {"text": text})


async def notify_discord(webhook_url: str, content: str) -> bool:
    """Send to Discord webhook."""
    return await notify_webhook(webhook_url, {"content": content})


async def send_all(conn, title: str, message: str, channels: list = None) -> dict:
    """Send via all configured channels."""
    if channels is None:
        channels = ["macos"]
    results = {}
    for ch in channels:
        if ch == "macos":
            results["macos"] = notify_macos(title, message)
        elif ch == "slack":
            url = db.get_config(conn, "slack_webhook")
            results["slack"] = await notify_slack(url, f"*{title}*\n{message}") if url else False
        elif ch == "discord":
            url = db.get_config(conn, "discord_webhook")
            results["discord"] = await notify_discord(url, f"**{title}**\n{message}") if url else False
    return results
