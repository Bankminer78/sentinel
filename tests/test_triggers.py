"""Tests for sentinel.triggers."""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from sentinel import triggers, db


@pytest.mark.asyncio
async def _noop():
    return True


def test_create_trigger(conn):
    tid = triggers.create_trigger(conn, "rule_violated", "notify",
                                  {"title": "Hi", "message": "test"})
    assert tid > 0


def test_create_trigger_invalid_event(conn):
    with pytest.raises(ValueError):
        triggers.create_trigger(conn, "bogus_event", "notify", {})


def test_create_trigger_invalid_action(conn):
    with pytest.raises(ValueError):
        triggers.create_trigger(conn, "morning", "bogus_action", {})


def test_get_triggers_all(conn):
    triggers.create_trigger(conn, "morning", "notify", {})
    triggers.create_trigger(conn, "evening", "notify", {})
    rows = triggers.get_triggers(conn)
    assert len(rows) == 2


def test_get_triggers_filter_event(conn):
    triggers.create_trigger(conn, "morning", "notify", {})
    triggers.create_trigger(conn, "evening", "notify", {})
    rows = triggers.get_triggers(conn, "morning")
    assert len(rows) == 1
    assert rows[0]["event"] == "morning"


def test_triggers_params_parsed(conn):
    triggers.create_trigger(conn, "morning", "notify",
                            {"title": "Hello", "message": "world"})
    rows = triggers.get_triggers(conn)
    assert rows[0]["params"]["title"] == "Hello"


def test_delete_trigger(conn):
    tid = triggers.create_trigger(conn, "morning", "notify", {})
    triggers.delete_trigger(conn, tid)
    assert triggers.get_triggers(conn) == []


def test_toggle_trigger(conn):
    tid = triggers.create_trigger(conn, "morning", "notify", {})
    triggers.toggle_trigger(conn, tid)
    rows = triggers.get_triggers(conn)
    assert rows[0]["active"] == 0
    triggers.toggle_trigger(conn, tid)
    rows = triggers.get_triggers(conn)
    assert rows[0]["active"] == 1


def test_fire_event_no_triggers(conn):
    res = asyncio.run(triggers.fire_event(conn, "morning"))
    assert res == []


def test_fire_event_notify(conn):
    triggers.create_trigger(conn, "morning", "notify",
                            {"title": "hi", "message": "m"})
    with patch("sentinel.notifications.notify_macos", return_value=True):
        res = asyncio.run(triggers.fire_event(conn, "morning"))
    assert len(res) == 1
    assert res[0]["result"]["ok"] is True


def test_fire_event_inactive_skipped(conn):
    tid = triggers.create_trigger(conn, "morning", "notify", {})
    triggers.toggle_trigger(conn, tid)
    with patch("sentinel.notifications.notify_macos", return_value=True):
        res = asyncio.run(triggers.fire_event(conn, "morning"))
    assert res == []


def test_fire_event_log_activity(conn):
    triggers.create_trigger(conn, "pomodoro_done", "log_activity",
                            {"app": "sentinel", "title": "done"})
    asyncio.run(triggers.fire_event(conn, "pomodoro_done"))
    acts = db.get_activities(conn)
    assert len(acts) == 1
    assert acts[0]["verdict"] == "trigger"


def test_fire_event_add_penalty(conn):
    triggers.create_trigger(conn, "rule_violated", "add_penalty",
                            {"rule_id": 1, "amount": 5.0})
    asyncio.run(triggers.fire_event(conn, "rule_violated"))
    n = conn.execute("SELECT COUNT(*) AS c FROM penalties").fetchone()["c"]
    assert n == 1


def test_fire_event_webhook(conn):
    triggers.create_trigger(conn, "focus_ended", "post_webhook",
                            {"url": "http://x", "payload": {"a": 1}})
    with patch("sentinel.notifications.notify_webhook",
               new=AsyncMock(return_value=True)):
        res = asyncio.run(triggers.fire_event(conn, "focus_ended"))
    assert res[0]["result"]["ok"] is True


def test_fire_event_slack_no_webhook(conn):
    triggers.create_trigger(conn, "morning", "send_slack", {"text": "hi"})
    res = asyncio.run(triggers.fire_event(conn, "morning"))
    assert res[0]["result"]["ok"] is False


def test_fire_event_slack_with_webhook(conn):
    db.set_config(conn, "slack_webhook", "http://slack")
    triggers.create_trigger(conn, "morning", "send_slack", {"text": "hi"})
    with patch("sentinel.notifications.notify_slack",
               new=AsyncMock(return_value=True)):
        res = asyncio.run(triggers.fire_event(conn, "morning"))
    assert res[0]["result"]["ok"] is True


def test_fire_event_context_merge(conn):
    triggers.create_trigger(conn, "rule_violated", "log_activity", {"app": "base"})
    asyncio.run(triggers.fire_event(conn, "rule_violated", {"title": "override"}))
    acts = db.get_activities(conn)
    assert acts[0]["title"] == "override"


def test_events_and_actions_lists():
    assert "morning" in triggers.EVENTS
    assert "notify" in triggers.ACTIONS
