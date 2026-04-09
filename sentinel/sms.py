"""SMS notifications via Twilio."""
import json
import httpx
from . import db, partners as partners_mod


def configure_twilio(conn, account_sid: str, auth_token: str, from_number: str) -> None:
    cfg = {"account_sid": account_sid, "auth_token": auth_token, "from_number": from_number}
    db.set_config(conn, "twilio_config", json.dumps(cfg))


def get_twilio_config(conn) -> dict:
    raw = db.get_config(conn, "twilio_config")
    return json.loads(raw) if raw else {}


async def send_sms(conn, to_number: str, message: str) -> bool:
    cfg = get_twilio_config(conn)
    if not cfg:
        return False
    url = f"https://api.twilio.com/2010-04-01/Accounts/{cfg['account_sid']}/Messages.json"
    data = {"From": cfg["from_number"], "To": to_number, "Body": message}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, data=data, auth=(cfg["account_sid"], cfg["auth_token"]))
            return r.status_code < 300
    except Exception:
        return False


async def send_alert_sms(conn, message: str) -> bool:
    any_ok = False
    for p in partners_mod.get_partners(conn):
        if p.get("method") == "sms":
            ok = await send_sms(conn, p["contact"], message)
            any_ok = any_ok or ok
    return any_ok


def test_twilio_config(conn) -> bool:
    cfg = get_twilio_config(conn)
    if not cfg:
        return False
    url = f"https://api.twilio.com/2010-04-01/Accounts/{cfg['account_sid']}.json"
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(url, auth=(cfg["account_sid"], cfg["auth_token"]))
            return r.status_code < 300
    except Exception:
        return False
