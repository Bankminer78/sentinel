"""Tests for sentinel.experiments."""
import time
import datetime as _dt
from unittest.mock import AsyncMock, patch
import pytest

from sentinel import experiments


def _log(conn, ts, domain, verdict, duration=60):
    conn.execute(
        "INSERT INTO activity_log (ts, app, title, url, domain, verdict, duration_s) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ts, "app", "t", f"https://{domain}", domain, verdict, duration))
    conn.commit()


def _seed_day(conn, date: _dt.date, productive=True):
    ts = _dt.datetime.combine(date, _dt.time(10, 0)).timestamp()
    if productive:
        _log(conn, ts, "work.com", "allow", duration=1800)
    else:
        conn.execute(
            "INSERT OR REPLACE INTO seen_domains (domain, category, first_seen) VALUES (?, ?, ?)",
            ("yt.com", "social", time.time()))
        conn.commit()
        _log(conn, ts, "yt.com", "block", duration=1800)


def test_start_experiment(conn):
    eid = experiments.start_experiment(conn, "no social", "avoid social media", 7)
    assert eid > 0


def test_get_experiment(conn):
    eid = experiments.start_experiment(conn, "e1", "hyp", 7)
    e = experiments.get_experiment(conn, eid)
    assert e["name"] == "e1"
    assert e["hypothesis"] == "hyp"
    assert e["status"] == "active"


def test_get_experiment_missing(conn):
    assert experiments.get_experiment(conn, 9999) is None


def test_list_experiments_empty(conn):
    assert experiments.list_experiments(conn) == []


def test_list_experiments(conn):
    experiments.start_experiment(conn, "a", "h", 3)
    experiments.start_experiment(conn, "b", "h", 3)
    assert len(experiments.list_experiments(conn)) == 2


def test_list_experiments_by_status(conn):
    experiments.start_experiment(conn, "a", "h", 3)
    active = experiments.list_experiments(conn, "active")
    assert len(active) == 1
    ended = experiments.list_experiments(conn, "ended")
    assert ended == []


def test_end_experiment(conn):
    eid = experiments.start_experiment(conn, "e", "h", 3)
    experiments.end_experiment(conn, eid)
    e = experiments.get_experiment(conn, eid)
    assert e["status"] == "ended"


def test_end_experiment_missing(conn):
    experiments.end_experiment(conn, 9999)  # no-op


def test_experiment_results_empty(conn):
    assert experiments.experiment_results(conn, 9999) == {}


def test_experiment_results_structure(conn):
    eid = experiments.start_experiment(conn, "e", "h", 3)
    r = experiments.experiment_results(conn, eid)
    for k in ("experiment_id", "name", "baseline_avg", "during_avg", "delta", "improved"):
        assert k in r


def test_experiment_baseline_captured(conn):
    # seed productive days in the last 14 days
    today = _dt.date.today()
    for i in range(1, 5):
        _seed_day(conn, today - _dt.timedelta(days=i), productive=True)
    eid = experiments.start_experiment(conn, "e", "h", 3)
    e = experiments.get_experiment(conn, eid)
    assert e["baseline_avg"] > 0


def test_experiment_results_ended(conn):
    eid = experiments.start_experiment(conn, "e", "h", 3)
    experiments.end_experiment(conn, eid)
    r = experiments.experiment_results(conn, eid)
    assert r["status"] == "ended"


def test_experiment_improved_flag(conn):
    eid = experiments.start_experiment(conn, "e", "h", 3)
    # Force during_avg > baseline_avg
    conn.execute("UPDATE experiments SET baseline_avg=50, during_avg=80 WHERE id=?", (eid,))
    conn.commit()
    r = experiments.experiment_results(conn, eid)
    assert r["improved"] is True
    assert r["delta"] == 30.0


def test_experiment_not_improved(conn):
    eid = experiments.start_experiment(conn, "e", "h", 3)
    conn.execute("UPDATE experiments SET baseline_avg=80, during_avg=50 WHERE id=?", (eid,))
    conn.commit()
    r = experiments.experiment_results(conn, eid)
    assert r["improved"] is False


@pytest.mark.asyncio
async def test_analyze_experiment(conn):
    eid = experiments.start_experiment(conn, "e", "test h", 3)
    with patch("sentinel.experiments.classifier.call_gemini",
               new_callable=AsyncMock, return_value="Looks promising."):
        r = await experiments.analyze_experiment(conn, eid, "fake-key")
        assert "promising" in r


@pytest.mark.asyncio
async def test_analyze_experiment_missing(conn):
    r = await experiments.analyze_experiment(conn, 9999, "fake-key")
    assert r == ""
