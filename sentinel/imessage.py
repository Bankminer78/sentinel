"""iMessage sensor — read-only views over ~/Library/Messages/chat.db.

The agent uses these to compose features like "popup if I'm messaging X"
without needing raw SQL access. All queries are read-only and scoped to
specific shapes; the chat.db file is opened in immutable mode so Messages.app
cannot collide with the read.

Privacy: nothing is stored. Each call reads chat.db live and returns. The
agent can persist findings via ai_store if it wants long-term tracking.

Permissions: macOS gates ~/Library/Messages with TCC ("Full Disk Access").
The Sentinel.app bundle (or terminal running the daemon) needs to be granted
access in System Settings → Privacy & Security → Full Disk Access. Without
that, every query returns ``{"error": "no access"}`` instead of crashing.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

CHAT_DB = Path.home() / "Library" / "Messages" / "chat.db"


def _open_readonly() -> sqlite3.Connection | None:
    """Open chat.db in immutable mode so Messages.app can't lock us out."""
    if not CHAT_DB.exists():
        return None
    try:
        # immutable=1 + mode=ro means we won't see updates after open, but
        # we also won't trip the writer. For polling sensors, that's fine.
        uri = f"file:{CHAT_DB}?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True, timeout=2)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error:
        return None


def _has_access() -> bool:
    """Check whether we can actually read chat.db (TCC granted)."""
    if not CHAT_DB.exists():
        return False
    try:
        with open(CHAT_DB, "rb") as f:
            f.read(16)  # SQLite magic header
        return True
    except (PermissionError, OSError):
        return False


def access_status() -> dict:
    """Diagnostic: is chat.db readable?"""
    return {
        "exists": CHAT_DB.exists(),
        "readable": _has_access(),
        "path": str(CHAT_DB),
    }


def current_chat() -> dict:
    """The most recently active chat thread.

    Returns:
        {"handle": "+15551234567", "service": "iMessage", "is_group": False,
         "last_message_ts": 1234567890.0, "last_text": "..."}
        or {"error": "no access"} / {"error": "no chats"}
    """
    if not _has_access():
        return {"error": "no access — grant Full Disk Access to read chat.db"}
    conn = _open_readonly()
    if not conn:
        return {"error": "could not open chat.db"}
    try:
        # Apple stores message dates as nanoseconds-since-2001-01-01 (Mac epoch)
        # Convert: unix_ts = mac_ns / 1e9 + 978307200
        row = conn.execute("""
            SELECT
                handle.id           AS handle,
                handle.service      AS service,
                chat.style          AS style,
                message.text        AS text,
                message.date / 1000000000.0 + 978307200 AS ts
            FROM message
            JOIN chat_message_join cmj ON cmj.message_id = message.ROWID
            JOIN chat                 ON chat.ROWID = cmj.chat_id
            JOIN chat_handle_join chj ON chj.chat_id = chat.ROWID
            JOIN handle               ON handle.ROWID = chj.handle_id
            WHERE message.text IS NOT NULL
            ORDER BY message.date DESC
            LIMIT 1
        """).fetchone()
        if not row:
            return {"error": "no chats"}
        return {
            "handle": row["handle"],
            "service": row["service"],
            "is_group": row["style"] == 43,  # 43 = group, 45 = 1:1
            "last_message_ts": row["ts"],
            "last_text": (row["text"] or "")[:200],
        }
    except sqlite3.Error as e:
        return {"error": f"sqlite error: {e}"}
    finally:
        conn.close()


def recent_chats(limit: int = 10) -> list:
    """Most recent chat threads, newest first.

    Returns: [{"handle", "service", "is_group", "last_message_ts", "last_text"}, ...]
    or [] on error.
    """
    if not _has_access():
        return []
    conn = _open_readonly()
    if not conn:
        return []
    try:
        rows = conn.execute("""
            SELECT
                handle.id   AS handle,
                handle.service AS service,
                chat.style  AS style,
                message.text AS text,
                MAX(message.date) / 1000000000.0 + 978307200 AS ts
            FROM message
            JOIN chat_message_join cmj ON cmj.message_id = message.ROWID
            JOIN chat                 ON chat.ROWID = cmj.chat_id
            JOIN chat_handle_join chj ON chj.chat_id = chat.ROWID
            JOIN handle               ON handle.ROWID = chj.handle_id
            WHERE message.text IS NOT NULL
            GROUP BY handle.id
            ORDER BY ts DESC
            LIMIT ?
        """, (int(limit),)).fetchall()
        return [
            {
                "handle": r["handle"],
                "service": r["service"],
                "is_group": r["style"] == 43,
                "last_message_ts": r["ts"],
                "last_text": (r["text"] or "")[:200],
            }
            for r in rows
        ]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def recent_messages(handle: str, limit: int = 20) -> list:
    """Recent messages with a specific handle (phone or email).

    Returns: [{"ts", "from_me", "text"}, ...] newest first, or [].
    """
    if not _has_access() or not handle:
        return []
    conn = _open_readonly()
    if not conn:
        return []
    try:
        rows = conn.execute("""
            SELECT
                message.text       AS text,
                message.is_from_me AS from_me,
                message.date / 1000000000.0 + 978307200 AS ts
            FROM message
            JOIN handle ON handle.ROWID = message.handle_id
            WHERE handle.id = ? AND message.text IS NOT NULL
            ORDER BY message.date DESC
            LIMIT ?
        """, (handle, int(limit))).fetchall()
        return [
            {"ts": r["ts"], "from_me": bool(r["from_me"]),
             "text": (r["text"] or "")[:500]}
            for r in rows
        ]
    except sqlite3.Error:
        return []
    finally:
        conn.close()
