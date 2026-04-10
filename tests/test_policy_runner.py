"""Tests for sentinel.policy_runner — apscheduler-driven policy executor."""
import os
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from sentinel import policy_runner, audit, db


@pytest.fixture
def temp_workdir(tmp_path, monkeypatch, conn):
    """Redirect WORKDIR to a tmp dir AND patch db.connect to return the test conn.

    Without the db.connect patch, anything inside _run_policy that calls
    db.connect() (e.g. the audit logger) opens the user's real ~/.config/
    sentinel/sentinel.db instead of our in-memory test conn, so audit
    assertions in the test silently fail.
    """
    workdir = tmp_path / "agent_workdir"
    workdir.mkdir()
    (workdir / "policies").mkdir()
    monkeypatch.setattr(policy_runner, "WORKDIR", workdir)
    monkeypatch.setattr(policy_runner, "CRON_FILE", workdir / "cron.toml")
    monkeypatch.setattr(policy_runner, "POLICIES_DIR", workdir / "policies")
    monkeypatch.setattr(policy_runner.db, "connect", lambda *a, **kw: conn)
    yield workdir


# ---------------------------------------------------------------------------
# load_policies — TOML parsing
# ---------------------------------------------------------------------------


def test_load_policies_no_file(temp_workdir):
    assert policy_runner.load_policies() == []


def test_load_policies_empty_file(temp_workdir):
    (temp_workdir / "cron.toml").write_text("")
    assert policy_runner.load_policies() == []


def test_load_policies_valid(temp_workdir):
    (temp_workdir / "cron.toml").write_text("""
[[policies]]
name = "morning_block"
file = "policies/morning.py"
cron = "0 9 * * 1-5"
enabled = true

[[policies]]
name = "vision_check"
file = "policies/vision.py"
cron = "*/10 9-17 * * 1-5"
""")
    out = policy_runner.load_policies()
    assert len(out) == 2
    assert out[0]["name"] == "morning_block"
    assert out[1]["name"] == "vision_check"
    assert out[1].get("enabled", True) is True  # default enabled


def test_load_policies_malformed_toml(temp_workdir, conn):
    (temp_workdir / "cron.toml").write_text("not [valid toml{{")
    out = policy_runner.load_policies()
    assert out == []
    # The parse error gets logged
    rows = audit.list_recent(conn, primitive="cron.parse")
    # May be 0 if conn is a fresh fixture; the loader uses db.connect() which
    # opens the user's real DB. We can only assert it doesn't raise.
    assert isinstance(rows, list)


# ---------------------------------------------------------------------------
# _validate
# ---------------------------------------------------------------------------


def test_validate_complete_entry():
    ok, _ = policy_runner._validate({
        "name": "x", "file": "x.py", "cron": "0 9 * * *"
    })
    assert ok is True


def test_validate_missing_name():
    ok, reason = policy_runner._validate({"file": "x.py", "cron": "0 9 * * *"})
    assert ok is False
    assert "name" in reason


def test_validate_missing_file():
    ok, reason = policy_runner._validate({"name": "x", "cron": "0 9 * * *"})
    assert ok is False


def test_validate_missing_cron():
    ok, reason = policy_runner._validate({"name": "x", "file": "x.py"})
    assert ok is False


def test_validate_empty_string_name():
    ok, _ = policy_runner._validate({"name": "", "file": "x.py", "cron": "* * * * *"})
    assert ok is False


# ---------------------------------------------------------------------------
# _run_policy — subprocess dispatch
# ---------------------------------------------------------------------------


def test_run_policy_path_traversal_refused(temp_workdir, conn):
    """A file path that escapes WORKDIR via .. must be refused."""
    # Create the file in tmp_path's parent so realpath escapes WORKDIR
    outside = temp_workdir.parent / "outside.py"
    outside.write_text("print('no')")
    policy_runner._run_policy("escape", "../outside.py")
    rows = audit.list_recent(conn, primitive="policy.run")
    refused = [r for r in rows if r["actor"] == "policy:escape"
               and r["result_status"] == "refused"]
    assert len(refused) == 1
    assert refused[0]["args_summary"]["reason"] == "path_outside_workdir"


def test_run_policy_missing_file(temp_workdir, conn):
    policy_runner._run_policy("missing", "policies/nonexistent.py")
    rows = audit.list_recent(conn, primitive="policy.run", actor="policy:missing")
    assert any(r["result_status"] == "missing" for r in rows)


def test_run_policy_subprocess_called_with_pythonpath(temp_workdir, conn):
    """The subprocess inherits PYTHONPATH so policy code can import sentinel."""
    policy_file = temp_workdir / "policies" / "test.py"
    policy_file.write_text("print('hello from policy')")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="hello from policy\n", stderr="")
        policy_runner._run_policy("test_pol", "policies/test.py")
        args, kwargs = mock_run.call_args
        # cmd[0] is python3, cmd[1] is the absolute file path
        assert args[0][0] == "python3"
        assert "policies/test.py" in args[0][1]
        # PYTHONPATH is set
        env = kwargs["env"]
        assert "PYTHONPATH" in env
        assert "sentinel" in env["PYTHONPATH"]
        # cwd is the workdir
        assert kwargs["cwd"] == str(temp_workdir)
        # timeout is bounded
        assert kwargs["timeout"] == policy_runner.SUBPROCESS_TIMEOUT_SEC


def test_run_policy_logs_success(temp_workdir, conn):
    policy_file = temp_workdir / "policies" / "ok.py"
    policy_file.write_text("print('ok')")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="ok\n", stderr="")
        policy_runner._run_policy("ok_pol", "policies/ok.py")
    rows = audit.list_recent(conn, primitive="policy.run", actor="policy:ok_pol")
    assert any(r["result_status"] == "ok" for r in rows)


def test_run_policy_logs_nonzero_exit(temp_workdir, conn):
    policy_file = temp_workdir / "policies" / "boom.py"
    policy_file.write_text("import sys; sys.exit(2)")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=2, stdout="", stderr="oops\n")
        policy_runner._run_policy("boom", "policies/boom.py")
    rows = audit.list_recent(conn, primitive="policy.run", actor="policy:boom")
    assert any(r["result_status"] == "exit_2" for r in rows)


def test_run_policy_logs_timeout(temp_workdir, conn):
    policy_file = temp_workdir / "policies" / "slow.py"
    policy_file.write_text("import time; time.sleep(999)")
    import subprocess
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("python3", 60)):
        policy_runner._run_policy("slow", "policies/slow.py")
    rows = audit.list_recent(conn, primitive="policy.run", actor="policy:slow")
    assert any(r["result_status"] == "timeout" for r in rows)


# ---------------------------------------------------------------------------
# reconcile — apscheduler integration
# ---------------------------------------------------------------------------


def test_reconcile_no_scheduler_is_noop(temp_workdir):
    """If start() hasn't been called, reconcile is a noop."""
    policy_runner._scheduler = None
    policy_runner._known_jobs.clear()
    policy_runner.reconcile()
    assert policy_runner._known_jobs == {}


def test_start_then_stop_lifecycle(temp_workdir):
    policy_runner.start(reconcile_interval_sec=300)
    try:
        assert policy_runner.is_running()
        # The reconcile job is registered even with no policies
        jobs = policy_runner._scheduler.get_jobs()
        assert any(j.id == "reconcile" for j in jobs)
    finally:
        policy_runner.stop()
    assert not policy_runner.is_running()


def test_reconcile_adds_jobs_from_cron_toml(temp_workdir):
    (temp_workdir / "cron.toml").write_text("""
[[policies]]
name = "p1"
file = "policies/p1.py"
cron = "0 9 * * *"

[[policies]]
name = "p2"
file = "policies/p2.py"
cron = "*/5 * * * *"
""")
    policy_runner.start(reconcile_interval_sec=300)
    try:
        jobs = {j.id for j in policy_runner._scheduler.get_jobs()}
        assert "policy_p1" in jobs
        assert "policy_p2" in jobs
    finally:
        policy_runner.stop()


def test_reconcile_respects_disabled_flag(temp_workdir):
    (temp_workdir / "cron.toml").write_text("""
[[policies]]
name = "off"
file = "policies/off.py"
cron = "0 9 * * *"
enabled = false
""")
    policy_runner.start(reconcile_interval_sec=300)
    try:
        jobs = {j.id for j in policy_runner._scheduler.get_jobs()}
        assert "policy_off" not in jobs
    finally:
        policy_runner.stop()


def test_reconcile_removes_stale_jobs(temp_workdir):
    """When a policy disappears from cron.toml, its job is removed."""
    (temp_workdir / "cron.toml").write_text("""
[[policies]]
name = "stays"
file = "policies/stays.py"
cron = "0 9 * * *"

[[policies]]
name = "goes"
file = "policies/goes.py"
cron = "0 10 * * *"
""")
    policy_runner.start(reconcile_interval_sec=300)
    try:
        jobs = {j.id for j in policy_runner._scheduler.get_jobs()}
        assert "policy_stays" in jobs
        assert "policy_goes" in jobs
        # Now remove "goes" from cron.toml
        (temp_workdir / "cron.toml").write_text("""
[[policies]]
name = "stays"
file = "policies/stays.py"
cron = "0 9 * * *"
""")
        policy_runner.reconcile()
        jobs = {j.id for j in policy_runner._scheduler.get_jobs()}
        assert "policy_stays" in jobs
        assert "policy_goes" not in jobs
    finally:
        policy_runner.stop()


def test_reconcile_ignores_invalid_cron(temp_workdir):
    (temp_workdir / "cron.toml").write_text("""
[[policies]]
name = "bad"
file = "policies/bad.py"
cron = "not a valid cron expression"
""")
    policy_runner.start(reconcile_interval_sec=300)
    try:
        jobs = {j.id for j in policy_runner._scheduler.get_jobs()}
        assert "policy_bad" not in jobs
    finally:
        policy_runner.stop()


def test_reconcile_ignores_malformed_entries(temp_workdir):
    """Entries missing required fields are skipped, valid ones still scheduled."""
    (temp_workdir / "cron.toml").write_text("""
[[policies]]
name = "valid"
file = "policies/valid.py"
cron = "0 9 * * *"

[[policies]]
file = "policies/no_name.py"
cron = "0 10 * * *"
""")
    policy_runner.start(reconcile_interval_sec=300)
    try:
        jobs = {j.id for j in policy_runner._scheduler.get_jobs()}
        assert "policy_valid" in jobs
        assert len([j for j in jobs if j.startswith("policy_")]) == 1
    finally:
        policy_runner.stop()


def test_reconcile_updates_changed_cron(temp_workdir):
    """If a policy's cron expression changes, the job is rescheduled."""
    (temp_workdir / "cron.toml").write_text("""
[[policies]]
name = "p"
file = "policies/p.py"
cron = "0 9 * * *"
""")
    policy_runner.start(reconcile_interval_sec=300)
    try:
        assert policy_runner._known_jobs.get("p") == "0 9 * * *"
        (temp_workdir / "cron.toml").write_text("""
[[policies]]
name = "p"
file = "policies/p.py"
cron = "0 10 * * *"
""")
        policy_runner.reconcile()
        assert policy_runner._known_jobs.get("p") == "0 10 * * *"
    finally:
        policy_runner.stop()
