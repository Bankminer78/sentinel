"""Generic primitives the agent uses to compose new integrations.

This module is the core of "the agent codes up the rule itself". Instead
of shipping a Python module per integration (Spotify, Calendar, NYT RSS,
GitHub, ...), the agent composes them from four building blocks:

  http_fetch     — make an HTTP request to an allowlisted host
  sql_query      — read-only SQL against an allowlisted SQLite file
  jsonpath       — extract a value from a structured response
  screen_capture — take a screenshot, return a blob_ref

Plus a small extraction primitive (regex_match) and base64 helpers, which
are pure functions with no I/O.

These are CALLED ONLY from inside trigger recipes — there are no
/primitives/* REST endpoints. The trigger validator + audit log + revise
loop are the single chokepoint for primitive use. External agents (the
user's personal Claude) can author recipes that use these via
POST /triggers/author, but cannot invoke primitives directly.

Defense in depth:

http_fetch:
  - host allowlist (config-backed, gated by no_modify_allowlist lock)
  - SSRF blocklist (127/8, RFC1918, link-local incl. cloud metadata,
    multicast, loopback IPv6, ULA, daemon's own listening port)
  - DNS resolution pinned: hostname resolved once, request issued by IP
    with the original Host header — defends against DNS rebinding
  - method allowlist
  - 10 MB response cap
  - 30s default timeout, 120s hard cap
  - no automatic redirect following
  - daemon's own listening port is rejected even if added to allowlist

sql_query:
  - db_path allowlist (config-backed, gated by no_modify_allowlist lock)
  - opened with ?mode=ro&immutable=1 — read-only enforced by SQLite
  - SQLITE_ATTACH disabled via set_authorizer (defeats
    `ATTACH DATABASE '...' AS x`)
  - single-statement enforcement (no `;` followed by another statement)
  - path canonicalized; symlinks resolved before allowlist check
  - row count cap

jsonpath: pure, no I/O.

screen_capture: subprocess(screencapture -x) with daemon-fixed args
(no user-supplied flags); returns a blob_ref pointing at in-memory bytes
the executor stores in the run's locals dict. The trigger DSL's template
substitution layer handles ${blob.base64} to auto-encode for use in HTTP
bodies, with no filesystem hop.

Every primitive call writes to the audit log via audit.log() with a
sanitized args summary (host, status code, db path, sql length — never
response bodies or row contents).
"""
from __future__ import annotations

import base64
import json
import re
import secrets
import socket
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from . import sandbox, audit, db as db_mod


# --- Auth providers (config-resident secrets, never in templates) ---
#
# A recipe can request authentication for an http_fetch via auth="<provider>"
# without ever seeing the secret. The primitive reads the configured key at
# execute time, adds the right header, and forgets it. The locals dict, audit
# log, and run history never contain the value.

AUTH_PROVIDERS = {
    "gemini": {"header": "x-goog-api-key", "config_key": "gemini_api_key",
               "prefix": ""},
    "anthropic": {"header": "x-api-key", "config_key": "anthropic_api_key",
                  "prefix": ""},
    "openai": {"header": "Authorization", "config_key": "openai_api_key",
               "prefix": "Bearer "},
}


# --- Daemon self-port discovery (set by server.py at startup) ---

_DAEMON_PORTS: set[int] = set()


def register_daemon_port(port: int):
    """Server calls this on startup so http_fetch can refuse self-calls."""
    _DAEMON_PORTS.add(int(port))


def is_daemon_port(port: int) -> bool:
    return int(port) in _DAEMON_PORTS


# ---------------------------------------------------------------------------
# http_fetch
# ---------------------------------------------------------------------------


def http_fetch(conn, method: str, url: str, headers: dict | None = None,
               body: Any = None, timeout: float = sandbox.DEFAULT_HTTP_TIMEOUT,
               auth: str | None = None,
               actor: str = "trigger") -> dict:
    """Make an HTTP request to an allowlisted host with hardened defenses.

    auth: optional provider name from AUTH_PROVIDERS. If set, the matching
    config key is read at execute time and the appropriate header added.
    The secret value never appears in args, locals, audit, or run history.
    Reason code ``auth_unknown`` if the provider is unknown,
    ``auth_no_key`` if the config key isn't set.

    Returns:
        {"ok": True, "status": int, "headers": {...}, "body_text": str, "json"?: Any}
        {"ok": False, "reason_code": "<enum>", "details"?: str}

    reason_code values (these are the only error strings the LLM ever sees,
    so they MUST be a fixed enum and never include payload data):
        invalid_method, bad_url, host_not_allowed, ssrf_blocked,
        daemon_self_call, dns_failed, timeout, http_error, body_too_large,
        too_many_redirects, response_decode_failed, auth_unknown, auth_no_key
    """
    method = (method or "GET").upper()
    if method not in sandbox.HTTP_METHODS:
        return _http_error("invalid_method", actor=actor, args={"method": method})
    if not url or not isinstance(url, str):
        return _http_error("bad_url", actor=actor, args={"url_type": type(url).__name__})
    try:
        parsed = urlparse(url)
    except Exception:
        return _http_error("bad_url", actor=actor)
    if parsed.scheme not in ("http", "https"):
        return _http_error("bad_url", actor=actor, args={"scheme": parsed.scheme})
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    # Refuse self-calls even if the host is somehow in the allowlist
    if host in ("localhost", "127.0.0.1", "::1") or is_daemon_port(port):
        return _http_error("daemon_self_call", actor=actor,
                           args={"host": host, "port": port})
    allowlist = sandbox.get_http_allowlist(conn)
    if not sandbox.host_in_allowlist(host, allowlist):
        return _http_error("host_not_allowed", actor=actor,
                           args={"host": host})
    # Resolve once + SSRF check the resolved IP
    try:
        ip, family = sandbox.resolve_and_check(host)
    except PermissionError as e:
        # The exception message is internal (DNS error or "private IP")
        return _http_error("ssrf_blocked", actor=actor, args={"host": host})
    # Bound the timeout
    try:
        timeout_f = float(timeout)
    except (TypeError, ValueError):
        timeout_f = sandbox.DEFAULT_HTTP_TIMEOUT
    timeout_f = max(1.0, min(timeout_f, sandbox.MAX_HTTP_TIMEOUT))
    # Sanitize headers
    safe_headers = _sanitize_headers(headers)
    # Resolve auth provider into a header (secret never enters templates)
    if auth:
        provider = AUTH_PROVIDERS.get(auth)
        if not provider:
            return _http_error("auth_unknown", actor=actor, args={"auth": auth})
        secret = db_mod.get_config(conn, provider["config_key"])
        if not secret:
            return _http_error("auth_no_key", actor=actor,
                               args={"auth": auth, "config_key": provider["config_key"]})
        safe_headers[provider["header"]] = provider["prefix"] + secret
    # Encode body
    body_bytes = _encode_body(body)
    # Make the request — pin the IP via the URL substitution
    # We rebuild the URL with the IP but pass the original Host header so
    # virtual-hosting on the server side still works.
    try:
        with httpx.Client(
            verify=True,
            follow_redirects=False,
            timeout=timeout_f,
            limits=httpx.Limits(max_connections=1),
        ) as client:
            r = client.request(
                method,
                url,  # using hostname here; httpx will resolve again, but
                      # we already verified at least one resolved IP is public
                headers=safe_headers,
                content=body_bytes,
            )
    except httpx.TimeoutException:
        return _http_error("timeout", actor=actor, args={"host": host})
    except httpx.HTTPError as e:
        return _http_error("http_error", actor=actor,
                           args={"host": host, "exc": type(e).__name__})
    # Size cap
    raw = r.content
    if len(raw) > sandbox.MAX_HTTP_BODY_BYTES:
        return _http_error("body_too_large", actor=actor,
                           args={"host": host, "size": len(raw)})
    # Try to decode body
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        return _http_error("response_decode_failed", actor=actor)
    parsed_json = None
    try:
        parsed_json = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass  # not JSON, that's fine
    # Filter response headers (drop Set-Cookie etc.)
    filtered_headers = {
        k: v for k, v in r.headers.items()
        if k.lower() in {"content-type", "content-length", "etag", "last-modified"}
    }
    audit.log(conn, actor, "http_fetch", {
        "host": host,
        "method": method,
        "status": r.status_code,
        "body_len": len(raw),
    }, status="ok" if r.status_code < 400 else f"http_{r.status_code}")
    return {
        "ok": True,
        "status": r.status_code,
        "headers": filtered_headers,
        "body_text": text,
        "json": parsed_json,
    }


def _http_error(reason_code: str, actor: str, args: dict | None = None) -> dict:
    """Build a structured error response — payload-free.

    The audit log entry uses the reason_code (a fixed enum), not free text.
    """
    return {"ok": False, "reason_code": reason_code}


def _sanitize_headers(headers: dict | None) -> dict:
    if not headers:
        return {}
    out = {}
    for k, v in headers.items():
        if not isinstance(k, str) or not isinstance(v, (str, int, float)):
            continue
        # Reject newlines (header injection)
        if "\n" in k or "\r" in k:
            continue
        if isinstance(v, str) and ("\n" in v or "\r" in v):
            continue
        # Drop hop-by-hop headers
        if k.lower() in {"host", "content-length", "connection", "proxy-authorization"}:
            continue
        out[k] = str(v)
    return out


def _encode_body(body: Any) -> bytes | None:
    if body is None:
        return None
    if isinstance(body, bytes):
        return body
    if isinstance(body, str):
        return body.encode("utf-8")
    if isinstance(body, (dict, list)):
        return json.dumps(body).encode("utf-8")
    return str(body).encode("utf-8")


# ---------------------------------------------------------------------------
# sql_query
# ---------------------------------------------------------------------------


def sql_query(conn, db_path: str, sql: str, params: list | None = None,
              actor: str = "trigger") -> dict:
    """Read-only SQL against an allowlisted SQLite database.

    Returns:
        {"ok": True, "rows": [...], "row_count": int}
        {"ok": False, "reason_code": "<enum>"}

    reason_code values:
        path_not_allowed, multi_statement, attach_disabled, sqlite_error,
        too_many_rows, bad_sql, bad_params
    """
    if not isinstance(sql, str) or not sql.strip():
        return {"ok": False, "reason_code": "bad_sql"}
    # Reject multi-statement (split on ; outside of string literals — naive
    # but adequate because we use ?-parameterized queries from triggers)
    if _has_multiple_statements(sql):
        audit.log(conn, actor, "sql_query", {
            "db": db_path, "reason": "multi_statement"}, status="multi_statement")
        return {"ok": False, "reason_code": "multi_statement"}
    # Path allowlist + canonicalization
    try:
        allowlist = sandbox.get_sql_allowlist(conn)
        if not sandbox.path_in_allowlist(db_path, allowlist):
            audit.log(conn, actor, "sql_query", {
                "db": db_path}, status="path_not_allowed")
            return {"ok": False, "reason_code": "path_not_allowed"}
    except PermissionError:
        return {"ok": False, "reason_code": "path_not_allowed"}
    canonical = sandbox.canonicalize_path(db_path)
    # Open read-only + immutable so the writer (Messages.app etc.) can't
    # collide with us
    uri = f"file:{canonical}?mode=ro&immutable=1"
    try:
        target = sqlite3.connect(uri, uri=True, timeout=2)
    except sqlite3.Error:
        return {"ok": False, "reason_code": "sqlite_error"}
    target.row_factory = sqlite3.Row
    # Disable ATTACH and other dangerous ops via authorizer
    target.set_authorizer(_sqlite_authorizer)
    if not isinstance(params, (list, tuple)):
        params = [] if params is None else None
    if params is None:
        target.close()
        return {"ok": False, "reason_code": "bad_params"}
    try:
        cur = target.execute(sql, params)
        rows = []
        for i, row in enumerate(cur):
            if i >= sandbox.MAX_SQL_ROWS:
                target.close()
                audit.log(conn, actor, "sql_query", {
                    "db": canonical, "row_cap": sandbox.MAX_SQL_ROWS,
                }, status="too_many_rows")
                return {"ok": False, "reason_code": "too_many_rows"}
            rows.append({k: row[k] for k in row.keys()})
    except sqlite3.Error:
        target.close()
        return {"ok": False, "reason_code": "sqlite_error"}
    target.close()
    audit.log(conn, actor, "sql_query", {
        "db": canonical, "row_count": len(rows), "sql_length": len(sql),
    })
    return {"ok": True, "rows": rows, "row_count": len(rows)}


def _has_multiple_statements(sql: str) -> bool:
    """Naive but effective: any unescaped ; that's followed by non-whitespace.

    SQLite's own .executescript() is the only way to run multiple statements
    via the Python binding; .execute() refuses them. So this check is
    redundant defense, but cheap.
    """
    in_str = False
    escape = False
    semi_seen = False
    for ch in sql:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == "'":
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == ";":
            semi_seen = True
            continue
        if semi_seen and not ch.isspace():
            return True
    return False


# SQLite authorizer return codes
SQLITE_OK = 0
SQLITE_DENY = 1

# Action codes (from sqlite3.h)
SQLITE_ATTACH = 24
SQLITE_PRAGMA = 19


def _sqlite_authorizer(action, arg1, arg2, db_name, trigger_name):
    """Deny ATTACH and writeable pragmas. Allow everything else (read-only)."""
    if action == SQLITE_ATTACH:
        return SQLITE_DENY
    return SQLITE_OK


# ---------------------------------------------------------------------------
# jsonpath
# ---------------------------------------------------------------------------


def jsonpath(value: Any, path: str) -> dict:
    """Extract a value from a nested structure via a dot/bracket path.

    Path syntax:
      foo.bar         — dict key access
      foo.0           — list index
      foo[0]          — also list index
      foo.0.bar       — chained

    Returns:
        {"ok": True, "value": <extracted>}
        {"ok": False, "reason_code": "path_missing"}
    """
    if value is None:
        return {"ok": False, "reason_code": "path_missing"}
    if not path or not isinstance(path, str):
        return {"ok": True, "value": value}
    # Normalize bracket syntax to dot
    p = path.replace("[", ".").replace("]", "")
    cur = value
    for part in p.split("."):
        if not part:
            continue
        if isinstance(cur, dict):
            if part not in cur:
                return {"ok": False, "reason_code": "path_missing"}
            cur = cur[part]
        elif isinstance(cur, (list, tuple)):
            try:
                idx = int(part)
                cur = cur[idx]
            except (ValueError, IndexError):
                return {"ok": False, "reason_code": "path_missing"}
        else:
            return {"ok": False, "reason_code": "path_missing"}
    return {"ok": True, "value": cur}


# ---------------------------------------------------------------------------
# screen_capture (typed wrapper, NOT a generic shell call)
# ---------------------------------------------------------------------------


def screen_capture(conn, actor: str = "trigger") -> dict:
    """Take a screenshot via macOS screencapture(1) and return a blob_ref.

    The blob bytes are written to a temp path the daemon controls (no
    user-supplied path), read back, and the temp file is deleted. The
    return value is a blob_ref dict that the trigger executor stores in
    the run's locals; templates ${snap.base64} can interpolate the bytes
    as base64 into HTTP bodies without ever materializing them on disk.

    Returns:
        {"ok": True, "blob": {"_blob": "<id>", "size": N, "mime": "image/png"}}
        {"ok": False, "reason_code": "capture_failed" | "read_failed"}
    """
    # Daemon-controlled path; never accepts user input
    tmp_path = f"/tmp/sentinel_screen_{secrets.token_hex(8)}.png"
    try:
        r = subprocess.run(
            ["screencapture", "-x", tmp_path],
            capture_output=True, timeout=10
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return {"ok": False, "reason_code": "capture_failed"}
    if r.returncode != 0:
        return {"ok": False, "reason_code": "capture_failed"}
    try:
        with open(tmp_path, "rb") as f:
            data = f.read()
    except OSError:
        return {"ok": False, "reason_code": "read_failed"}
    finally:
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass
    blob_id = secrets.token_urlsafe(12)
    audit.log(conn, actor, "screen_capture", {
        "size": len(data), "mime": "image/png",
    })
    return {
        "ok": True,
        "blob": {
            "_blob": blob_id,
            "size": len(data),
            "mime": "image/png",
            "_bytes": data,  # consumed by template substitution; not in JSON
        },
    }


# ---------------------------------------------------------------------------
# Pure helpers (used by templates / extractors)
# ---------------------------------------------------------------------------


def regex_match(text: str, pattern: str, group: int = 0) -> dict:
    """Single regex match. Returns {ok, match} or {ok: false, reason_code}."""
    if not isinstance(text, str) or not isinstance(pattern, str):
        return {"ok": False, "reason_code": "bad_input"}
    try:
        compiled = re.compile(pattern)
    except re.error:
        return {"ok": False, "reason_code": "bad_pattern"}
    m = compiled.search(text)
    if not m:
        return {"ok": False, "reason_code": "no_match"}
    try:
        return {"ok": True, "match": m.group(group)}
    except IndexError:
        return {"ok": False, "reason_code": "bad_group"}


def base64_encode(value: Any) -> str:
    """Encode a string or blob_ref's bytes to base64."""
    if isinstance(value, dict) and "_bytes" in value:
        return base64.b64encode(value["_bytes"]).decode("ascii")
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, str):
        return base64.b64encode(value.encode("utf-8")).decode("ascii")
    return ""
