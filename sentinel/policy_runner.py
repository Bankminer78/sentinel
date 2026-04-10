"""Scheduled policy executor.

For "do this every weekday morning" type tasks, Claude writes a Python file
to ``~/.config/sentinel/agent_workdir/policies/<name>.py`` and registers it
in ``~/.config/sentinel/agent_workdir/cron.toml`` with a cron expression:

    [[policies]]
    name = "no_youtube_morning"
    file = "policies/no_youtube_morning.py"
    cron = "0 9 * * 1-5"
    enabled = true

This module is the apscheduler loop that reads cron.toml on every scheduler
tick, schedules each enabled policy with its cron, and runs each entry as a
subprocess (`python <file>`) at its scheduled time. The subprocess inherits
PYTHONPATH so the policy file can `from sentinel import ...`.

Pure Python execution. No Claude in the loop. Each policy run is logged to
the audit table with actor=`"policy:<name>"`.

Failures don't bring the daemon down — each policy run is wrapped in a
try/except, errors are logged to the audit table, and the next scheduled
tick proceeds normally.
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

try:
    import tomllib  # py3.11+
except ImportError:
    import tomli as tomllib  # type: ignore

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from . import db, audit


WORKDIR = Path.home() / ".config" / "sentinel" / "agent_workdir"
SENTINEL_REPO = Path(__file__).resolve().parent.parent
CRON_FILE = WORKDIR / "cron.toml"
POLICIES_DIR = WORKDIR / "policies"
SUBPROCESS_TIMEOUT_SEC = 60

_scheduler: BackgroundScheduler | None = None
_known_jobs: dict[str, str] = {}  # name → cron string we last registered
_lock = threading.Lock()


# --- Subprocess runner: this is what apscheduler invokes per tick ---


def _run_policy(name: str, file_rel: str):
    """Run one policy script as a subprocess. Always logs to audit."""
    started = time.time()
    abs_path = (WORKDIR / file_rel).resolve()
    if WORKDIR not in abs_path.parents:
        # Path traversal attempt — refuse and log
        try:
            conn = db.connect()
            audit.log(conn, f"policy:{name}", "policy.run",
                      {"file": file_rel, "reason": "path_outside_workdir"},
                      status="refused")
        except Exception:
            pass
        return
    if not abs_path.exists():
        try:
            conn = db.connect()
            audit.log(conn, f"policy:{name}", "policy.run",
                      {"file": file_rel, "reason": "file_missing"},
                      status="missing")
        except Exception:
            pass
        return
    env = {**os.environ, "PYTHONPATH": str(SENTINEL_REPO)}
    try:
        proc = subprocess.run(
            ["python3", str(abs_path)],
            cwd=str(WORKDIR),
            capture_output=True, text=True,
            timeout=SUBPROCESS_TIMEOUT_SEC,
            env=env,
        )
        duration_ms = (time.time() - started) * 1000
        try:
            conn = db.connect()
            audit.log(conn, f"policy:{name}", "policy.run", {
                "file": file_rel,
                "duration_ms": round(duration_ms),
                "exit_code": proc.returncode,
                "stdout_len": len(proc.stdout),
                "stderr_len": len(proc.stderr),
            }, status="ok" if proc.returncode == 0 else f"exit_{proc.returncode}")
        except Exception:
            pass
    except subprocess.TimeoutExpired:
        try:
            conn = db.connect()
            audit.log(conn, f"policy:{name}", "policy.run",
                      {"file": file_rel, "timeout_sec": SUBPROCESS_TIMEOUT_SEC},
                      status="timeout")
        except Exception:
            pass
    except Exception as e:
        try:
            conn = db.connect()
            audit.log(conn, f"policy:{name}", "policy.run",
                      {"file": file_rel, "exc_type": type(e).__name__,
                       "exc_msg": str(e)[:200]},
                      status="error")
        except Exception:
            pass


# --- cron.toml parsing + scheduling ---


def load_policies() -> list[dict[str, Any]]:
    """Read cron.toml and return the list of policy entries.

    Robust to a missing or malformed file (returns empty list and logs).
    """
    if not CRON_FILE.exists():
        return []
    try:
        with open(CRON_FILE, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        try:
            conn = db.connect()
            audit.log(conn, "policy_runner", "cron.parse",
                      {"exc_type": type(e).__name__, "exc_msg": str(e)[:200]},
                      status="error")
        except Exception:
            pass
        return []
    return data.get("policies", []) or []


def _validate(policy: dict) -> tuple[bool, str]:
    if not isinstance(policy.get("name"), str) or not policy["name"]:
        return False, "name required"
    if not isinstance(policy.get("file"), str) or not policy["file"]:
        return False, "file required"
    if not isinstance(policy.get("cron"), str) or not policy["cron"]:
        return False, "cron required"
    return True, ""


def reconcile():
    """Sync the apscheduler job set with the policies in cron.toml.

    Add new ones, update changed schedules, remove deleted ones.
    Called on startup and on every scheduler tick (cheap — small file).
    """
    global _known_jobs
    if _scheduler is None:
        return
    with _lock:
        policies = load_policies()
        seen: set[str] = set()
        for policy in policies:
            ok, reason = _validate(policy)
            if not ok:
                continue
            if not policy.get("enabled", True):
                continue
            name = policy["name"]
            file_rel = policy["file"]
            cron = policy["cron"]
            seen.add(name)
            if _known_jobs.get(name) == cron:
                continue  # already scheduled with this cron
            try:
                trigger = CronTrigger.from_crontab(cron)
            except Exception:
                continue
            try:
                _scheduler.remove_job(f"policy_{name}")
            except Exception:
                pass
            _scheduler.add_job(
                _run_policy,
                trigger,
                args=(name, file_rel),
                id=f"policy_{name}",
                replace_existing=True,
                misfire_grace_time=60,
            )
            _known_jobs[name] = cron
        # Drop jobs whose policies have been removed
        stale = set(_known_jobs.keys()) - seen
        for name in stale:
            try:
                _scheduler.remove_job(f"policy_{name}")
            except Exception:
                pass
            _known_jobs.pop(name, None)


# --- Public lifecycle ---


def start(reconcile_interval_sec: int = 30):
    """Start the apscheduler in the background and the reconcile loop."""
    global _scheduler
    if _scheduler is not None:
        return
    WORKDIR.mkdir(parents=True, exist_ok=True)
    POLICIES_DIR.mkdir(exist_ok=True)
    _scheduler = BackgroundScheduler()
    _scheduler.start()
    reconcile()
    _scheduler.add_job(
        reconcile,
        trigger="interval",
        seconds=reconcile_interval_sec,
        id="reconcile",
    )


def stop():
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
    _known_jobs.clear()


def is_running() -> bool:
    return _scheduler is not None and _scheduler.running
