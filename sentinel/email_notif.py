"""Email notifications via SMTP."""
import smtplib, ssl, json, asyncio
from email.message import EmailMessage
from . import db


def configure_email(conn, smtp_host: str, smtp_port: int, username: str,
                    password: str, from_addr: str) -> None:
    cfg = {
        "smtp_host": smtp_host, "smtp_port": int(smtp_port),
        "username": username, "password": password, "from_addr": from_addr,
    }
    db.set_config(conn, "email_config", json.dumps(cfg))


def get_email_config(conn) -> dict:
    raw = db.get_config(conn, "email_config")
    return json.loads(raw) if raw else {}


def _build_message(cfg: dict, to: str, subject: str, body: str, html: bool) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.get("from_addr", cfg.get("username", ""))
    msg["To"] = to
    if html:
        msg.set_content("HTML mail — view in an HTML client.")
        msg.add_alternative(body, subtype="html")
    else:
        msg.set_content(body)
    return msg


def send_email(conn, to: str, subject: str, body: str, html: bool = False) -> bool:
    cfg = get_email_config(conn)
    if not cfg:
        return False
    try:
        msg = _build_message(cfg, to, subject, body, html)
        context = ssl.create_default_context()
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as server:
            server.starttls(context=context)
            server.login(cfg["username"], cfg["password"])
            server.send_message(msg)
        return True
    except Exception:
        return False


async def send_email_async(conn, to: str, subject: str, body: str) -> bool:
    return await asyncio.get_event_loop().run_in_executor(
        None, send_email, conn, to, subject, body, False)


def send_digest_email(conn, to: str, digest_text: str) -> bool:
    return send_email(conn, to, "Sentinel Daily Digest", digest_text, html=False)


def test_email_config(conn) -> bool:
    cfg = get_email_config(conn)
    if not cfg:
        return False
    try:
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=10) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(cfg["username"], cfg["password"])
        return True
    except Exception:
        return False
