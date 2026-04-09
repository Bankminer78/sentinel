"""Tests for sentinel.patterns."""
import pytest
import time
import datetime as _dt
from sentinel import patterns, db


def _log(conn, ts, domain, verdict):
    conn.execute(
        "INSERT INTO activity_log (ts, app, title, url, domain, verdict) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (ts, "app", "title", f"https://{domain}", domain, verdict))
    conn.commit()


def test_daily_patterns_empty(conn):
    r = patterns.find_daily_patterns(conn)
    assert r == {"distracted_by_hour": {}, "productive_by_hour": {}}


def test_daily_patterns_counts(conn):
    base = _dt.datetime(2024, 1, 1, 14, 0, 0).timestamp()
    _log(conn, base, "yt.com", "block")
    _log(conn, base + 10, "yt.com", "block")
    _log(conn, base + 20, "gh.com", "allow")
    r = patterns.find_daily_patterns(conn)
    assert r["distracted_by_hour"][14] == 2
    assert r["productive_by_hour"][14] == 1


def test_site_pairs_empty(conn):
    assert patterns.find_site_pairs(conn) == []


def test_site_pairs_basic(conn):
    now = time.time()
    _log(conn, now, "a.com", "allow")
    _log(conn, now + 10, "b.com", "allow")
    _log(conn, now + 20, "a.com", "allow")
    _log(conn, now + 30, "b.com", "allow")
    pairs = patterns.find_site_pairs(conn)
    assert any(sorted(p["pair"]) == ["a.com", "b.com"] for p in pairs)


def test_site_pairs_gap_excludes(conn):
    now = time.time()
    _log(conn, now, "a.com", "allow")
    _log(conn, now + 10000, "b.com", "allow")
    pairs = patterns.find_site_pairs(conn)
    assert pairs == []


def test_distraction_chains_none(conn):
    assert patterns.find_distraction_chains(conn) == []


def test_distraction_chains_basic(conn):
    now = time.time()
    _log(conn, now, "a.com", "block")
    _log(conn, now + 1, "b.com", "block")
    _log(conn, now + 2, "c.com", "block")
    _log(conn, now + 3, "d.com", "allow")
    chains = patterns.find_distraction_chains(conn)
    assert len(chains) == 1
    assert chains[0]["length"] == 3


def test_distraction_chains_tail(conn):
    now = time.time()
    _log(conn, now, "a.com", "block")
    _log(conn, now + 1, "b.com", "block")
    chains = patterns.find_distraction_chains(conn)
    assert len(chains) == 1


def test_work_sessions_empty(conn):
    assert patterns.find_work_sessions(conn) == []


def test_work_sessions_single(conn):
    now = time.time()
    _log(conn, now, "a.com", "allow")
    _log(conn, now + 30, "a.com", "allow")
    _log(conn, now + 60, "a.com", "allow")
    sessions = patterns.find_work_sessions(conn)
    assert len(sessions) == 1
    assert sessions[0]["duration_s"] == 60


def test_work_sessions_split(conn):
    now = time.time()
    _log(conn, now, "a.com", "allow")
    _log(conn, now + 30, "a.com", "allow")
    _log(conn, now + 1000, "a.com", "allow")
    _log(conn, now + 1030, "a.com", "allow")
    sessions = patterns.find_work_sessions(conn)
    assert len(sessions) == 2


def test_interruptions_empty(conn):
    assert patterns.find_interruptions(conn) == []


def test_interruptions_basic(conn):
    now = time.time()
    _log(conn, now, "a.com", "allow")
    _log(conn, now + 1, "yt.com", "block")
    _log(conn, now + 2, "a.com", "allow")
    interruptions = patterns.find_interruptions(conn)
    assert len(interruptions) == 1
    assert interruptions[0]["domain"] == "yt.com"


def test_peak_distraction_hour_none(conn):
    assert patterns.peak_distraction_hour(conn) == -1


def test_peak_distraction_hour(conn):
    b10 = _dt.datetime(2024, 1, 1, 10, 0, 0).timestamp()
    b15 = _dt.datetime(2024, 1, 1, 15, 0, 0).timestamp()
    _log(conn, b10, "x", "block")
    _log(conn, b15, "x", "block")
    _log(conn, b15 + 10, "x", "block")
    assert patterns.peak_distraction_hour(conn) == 15


def test_session_length_distribution_empty(conn):
    assert patterns.session_length_distribution(conn) == {}


def test_session_length_distribution(conn):
    base = _dt.datetime(2024, 1, 1, 9, 0, 0).timestamp()
    _log(conn, base, "a.com", "allow")
    _log(conn, base + 60, "a.com", "allow")
    dist = patterns.session_length_distribution(conn)
    assert 9 in dist
