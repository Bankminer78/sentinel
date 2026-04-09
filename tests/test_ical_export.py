"""Tests for sentinel.ical_export."""
import json
import time
import pytest
from sentinel import ical_export, db


def test_format_ical_event_basic():
    out = ical_export.format_ical_event("u1", "Test", 1_700_000_000, 1_700_003_600, "desc")
    assert "BEGIN:VEVENT" in out
    assert "END:VEVENT" in out
    assert "UID:u1" in out
    assert "SUMMARY:Test" in out
    assert "DESCRIPTION:desc" in out


def test_format_ical_event_no_description():
    out = ical_export.format_ical_event("u1", "Test", 1_700_000_000, 1_700_003_600)
    assert "DESCRIPTION" not in out


def test_format_ical_event_escapes_special():
    out = ical_export.format_ical_event("u1", "A, B; C", 1_700_000_000, 1_700_003_600)
    assert "A\\, B\\; C" in out


def test_ts_to_ical_format():
    s = ical_export._ts_to_ical(1_700_000_000)
    assert s.endswith("Z")
    assert "T" in s
    assert len(s) == 16


def test_focus_sessions_to_ical_empty(conn):
    out = ical_export.focus_sessions_to_ical(conn)
    assert "BEGIN:VCALENDAR" in out
    assert "END:VCALENDAR" in out


def test_focus_sessions_to_ical_with_data(conn):
    now = time.time()
    sid = db.save_focus_session(conn, now, 25, True)
    db.end_focus(conn, sid, now + 1500)
    out = ical_export.focus_sessions_to_ical(conn)
    assert "Focus Session" in out
    assert f"focus-{sid}@sentinel" in out


def test_focus_sessions_not_ended(conn):
    now = time.time()
    db.save_focus_session(conn, now, 25, True)
    out = ical_export.focus_sessions_to_ical(conn)
    assert "Focus Session" in out
    assert out.count("BEGIN:VEVENT") == 1


def test_pomodoros_to_ical_empty(conn):
    out = ical_export.pomodoros_to_ical(conn)
    assert "BEGIN:VCALENDAR" in out
    assert "BEGIN:VEVENT" not in out


def test_pomodoros_to_ical_with_data(conn):
    pid = db.save_pomodoro(conn, time.time(), 25, 5, 4)
    out = ical_export.pomodoros_to_ical(conn)
    assert f"pomo-{pid}@sentinel" in out
    assert "Pomodoro x4" in out


def test_pomodoros_to_ical_skips_old(conn):
    db.save_pomodoro(conn, time.time() - 40 * 86400, 25, 5, 4)
    out = ical_export.pomodoros_to_ical(conn, days=30)
    assert "BEGIN:VEVENT" not in out


def test_blocks_to_ical_empty(conn):
    out = ical_export.blocks_to_ical(conn)
    assert "BEGIN:VCALENDAR" in out
    assert "BEGIN:VEVENT" not in out


def test_blocks_to_ical_with_schedule(conn):
    rid = db.add_rule(conn, "block reddit", parsed={"schedule": {"start": "09:00", "end": "17:00"}})
    out = ical_export.blocks_to_ical(conn)
    assert f"rule-{rid}@sentinel" in out
    assert "Block: block reddit" in out


def test_blocks_to_ical_skips_unscheduled(conn):
    db.add_rule(conn, "blanket block", parsed={})
    out = ical_export.blocks_to_ical(conn)
    assert "BEGIN:VEVENT" not in out


def test_full_calendar_export_combines(conn):
    db.save_focus_session(conn, time.time(), 10, True)
    db.save_pomodoro(conn, time.time(), 25, 5, 2)
    db.add_rule(conn, "no YT", parsed={"schedule": {"start": "09:00", "end": "17:00"}})
    out = ical_export.full_calendar_export(conn)
    assert "BEGIN:VCALENDAR" in out
    assert out.count("BEGIN:VEVENT") >= 3
    assert out.count("END:VCALENDAR") == 1


def test_full_calendar_export_empty(conn):
    out = ical_export.full_calendar_export(conn)
    assert "BEGIN:VCALENDAR" in out
    assert "END:VCALENDAR" in out
