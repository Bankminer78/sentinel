"""Sandbox helpers for the generic primitives.

Holds the allowlist storage (config-table backed) and the security
helpers each primitive uses: path canonicalization, IP-address checks
for SSRF defense, ATTACH-disabling SQLite authorizer, etc.

The allowlists are config keys editable via the /sandbox/* server
endpoints. Each is gated by the no_modify_allowlist lock kind, so the
user can commit to "no extending the allowlist for the next N hours".

Defaults are conservative: only the well-known LLM provider hosts for
http_fetch, and an EMPTY sql allowlist (chat.db is NOT in the default —
it stays behind the imessage_* macros). The user must opt in to any
local DB before sql_query can read it.
"""
from __future__ import annotations

import ipaddress
import json
import os
import socket
from pathlib import Path

from . import db


# --- Defaults ---

DEFAULT_HTTP_HOSTS = [
    "generativelanguage.googleapis.com",
    "api.anthropic.com",
    "api.openai.com",
]

DEFAULT_SQL_DB_PATHS: list[str] = []

# Methods that can mutate the remote — allowed but flagged in audit.
HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"}

MAX_HTTP_BODY_BYTES = 10 * 1024 * 1024  # 10 MB
DEFAULT_HTTP_TIMEOUT = 30
MAX_HTTP_TIMEOUT = 120
MAX_SQL_ROWS = 1000


# --- Allowlist storage ---

def get_http_allowlist(conn) -> list[str]:
    raw = db.get_config(conn, "http_allowlist")
    if not raw:
        return list(DEFAULT_HTTP_HOSTS)
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return list(DEFAULT_HTTP_HOSTS)


def set_http_allowlist(conn, hosts: list[str]):
    if not isinstance(hosts, list) or not all(isinstance(h, str) and h for h in hosts):
        raise ValueError("hosts must be a list of non-empty strings")
    _check_no_modify_lock(conn)
    db.set_config(conn, "http_allowlist", json.dumps(hosts))


def get_sql_allowlist(conn) -> list[str]:
    raw = db.get_config(conn, "sql_allowlist")
    if not raw:
        return list(DEFAULT_SQL_DB_PATHS)
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return list(DEFAULT_SQL_DB_PATHS)


def set_sql_allowlist(conn, paths: list[str]):
    if not isinstance(paths, list) or not all(isinstance(p, str) and p for p in paths):
        raise ValueError("paths must be a list of non-empty strings")
    _check_no_modify_lock(conn)
    # Canonicalize on write so the read path doesn't have to.
    canonical = []
    for p in paths:
        try:
            canonical.append(str(Path(p).expanduser().resolve()))
        except (OSError, RuntimeError):
            raise ValueError(f"could not canonicalize path: {p}")
    db.set_config(conn, "sql_allowlist", json.dumps(canonical))


def _check_no_modify_lock(conn):
    """Refuse the modification if a no_modify_allowlist lock is active."""
    from . import locks
    if locks.is_locked(conn, "no_modify_allowlist"):
        raise PermissionError("no_modify_allowlist lock is active")


# --- Host / IP defense (SSRF) ---

PRIVATE_NETS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local + cloud metadata
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),  # CGNAT
    ipaddress.ip_network("224.0.0.0/4"),    # multicast
    ipaddress.ip_network("240.0.0.0/4"),    # reserved
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fc00::/7"),
]


def is_private_ip(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return True  # if we can't parse it, treat as unsafe
    for net in PRIVATE_NETS:
        if ip in net:
            return True
    return False


def resolve_and_check(host: str) -> tuple[str, int]:
    """Resolve a hostname once and return (ip, family).

    Raises PermissionError if the resolved IP is in any private/reserved
    range. The pinned IP is returned so the caller can connect by IP and
    pass the original Host header — defending against DNS rebinding
    (attacker controls DNS, returns public IP at resolve time then private
    at connect time).
    """
    if not host:
        raise PermissionError("empty host")
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise PermissionError(f"DNS resolution failed: {e}")
    for family, _, _, _, sockaddr in infos:
        addr = sockaddr[0]
        if not is_private_ip(addr):
            return addr, family
    raise PermissionError(f"all resolved IPs for {host} are private/reserved")


def host_in_allowlist(host: str, allowlist: list[str]) -> bool:
    """Match a host against the allowlist.

    Exact match required. No wildcard subdomains — if the user wants to
    allow ``api.example.com``, they must list it explicitly.
    """
    if not host or not allowlist:
        return False
    h = host.lower().strip()
    return h in {a.lower().strip() for a in allowlist}


# --- Path canonicalization (file/sql primitives) ---

def canonicalize_path(path: str) -> str:
    """Resolve ~, symlinks, and ../ to a real absolute path.

    Note: this is a TOCTOU-prone operation. The caller should open the
    file with O_NOFOLLOW or a similar mechanism if it cares about the
    race between this resolution and the actual open. For sql_query, the
    SQLite open will fail later if the file disappears or becomes a
    different inode, which is acceptable for the read-only sensor case.
    """
    p = Path(path).expanduser()
    try:
        return str(p.resolve(strict=False))
    except (OSError, RuntimeError):
        raise PermissionError(f"could not canonicalize: {path}")


def path_in_allowlist(path: str, allowlist: list[str]) -> bool:
    """The canonicalized path must EXACTLY match an entry in the allowlist.

    No prefix matching, no wildcard. The user must list each db they
    want to expose. This is annoying but it's the only way to be sure
    the agent can't escape via symlink + glob.
    """
    if not path or not allowlist:
        return False
    canonical = canonicalize_path(path)
    allow_set = {canonicalize_path(a) for a in allowlist}
    return canonical in allow_set
