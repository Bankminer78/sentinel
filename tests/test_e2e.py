"""End-to-end stress tests for the Sentinel FastAPI server.

Exercises every major endpoint against an in-memory database via the
FastAPI TestClient, checking the full server + DB integration path.
"""

import sqlite3
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from sentinel import blocker, db, monitor
from sentinel.server import app


def _make_test_conn():
    """Create an in-memory SQLite connection with the core tables.

    Tables used by modules with lazy ``_ensure_table`` helpers are NOT
    created here — they come into existence on first call.
    """
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY, text TEXT NOT NULL, parsed TEXT DEFAULT '{}',
            action TEXT DEFAULT 'block', active INTEGER DEFAULT 1,
            created_at REAL
        );
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY, ts REAL, app TEXT, title TEXT,
            url TEXT, domain TEXT, verdict TEXT, rule_id INTEGER,
            duration_s REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS seen_domains (
            domain TEXT PRIMARY KEY, category TEXT, first_seen REAL
        );
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY, value TEXT
        );
        CREATE TABLE IF NOT EXISTS pomodoro_sessions (
            id INTEGER PRIMARY KEY, start_ts REAL,
            work_minutes INTEGER, break_minutes INTEGER,
            total_cycles INTEGER, current_cycle INTEGER DEFAULT 1,
            state TEXT DEFAULT 'work', ended_at REAL
        );
        CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY, start_ts REAL,
            duration_minutes INTEGER, locked INTEGER DEFAULT 1,
            ended_at REAL
        );
        CREATE TABLE IF NOT EXISTS allowance_log (
            id INTEGER PRIMARY KEY, rule_id INTEGER,
            date TEXT, seconds_used INTEGER DEFAULT 0,
            UNIQUE(rule_id, date)
        );
        CREATE TABLE IF NOT EXISTS interventions (
            id INTEGER PRIMARY KEY, kind TEXT, context TEXT, state TEXT,
            created_at REAL, completed_at REAL, passed INTEGER, attempts INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY, name TEXT, target_type TEXT,
            target_value INTEGER, category TEXT, created_at REAL
        );
        CREATE TABLE IF NOT EXISTS streaks (
            goal_name TEXT PRIMARY KEY, current INTEGER DEFAULT 0,
            longest INTEGER DEFAULT 0, last_date TEXT
        );
        """
    )
    return conn


@pytest.fixture
def client():
    """FastAPI TestClient wired up to an isolated in-memory DB."""
    import sentinel.server as srv

    # Reset any cross-test state in global stores.
    blocker._blocked_domains.clear()

    c = _make_test_conn()
    db.set_config(c, "gemini_api_key", "test-key")
    srv.conn = c
    with patch.object(blocker, "_sync_hosts"), \
         patch("sentinel.server.startup"), \
         patch.object(monitor, "start"):
        with TestClient(app, raise_server_exceptions=True) as tc:
            srv.conn = c
            yield tc
    c.close()
    srv.conn = None
    blocker._blocked_domains.clear()


# ---------------------------------------------------------------------------
# Rules: create / list / verify the DB round-trip
# ---------------------------------------------------------------------------


class TestRulesFlow:
    def test_create_rule_returns_id(self, client):
        with patch("sentinel.classifier.parse_rule", new_callable=AsyncMock,
                   return_value={"domains": ["twitter.com"], "action": "block"}):
            r = client.post("/rules", json={"text": "Block Twitter"})
        assert r.status_code == 200
        data = r.json()
        assert data["id"] > 0
        assert data["text"] == "Block Twitter"
        assert data["parsed"]["domains"] == ["twitter.com"]

    def test_list_rules_after_create(self, client):
        with patch("sentinel.classifier.parse_rule", new_callable=AsyncMock, return_value={}):
            client.post("/rules", json={"text": "No YouTube"})
            client.post("/rules", json={"text": "No Reddit"})
        rules = client.get("/rules").json()
        assert len(rules) == 2
        assert {r["text"] for r in rules} == {"No YouTube", "No Reddit"}

    def test_create_rule_when_llm_fails(self, client):
        """If parse_rule raises (bad API key, network error, etc.) the
        endpoint must still persist the raw rule text with empty parsed."""
        with patch("sentinel.classifier.parse_rule", new_callable=AsyncMock,
                   side_effect=RuntimeError("api down")):
            r = client.post("/rules", json={"text": "Block Twitter"})
        assert r.status_code == 200
        data = r.json()
        assert data["id"] > 0
        assert data["text"] == "Block Twitter"
        assert data["parsed"] == {}


# ---------------------------------------------------------------------------
# Activity endpoint
# ---------------------------------------------------------------------------


class TestActivityFlow:
    def test_activity_returns_verdict(self, client):
        r = client.post("/activity", json={
            "url": "https://github.com/readme",
            "title": "Repo",
            "domain": "github.com",
        })
        assert r.status_code == 200
        assert r.json()["verdict"] in ("allow", "block", "warn")

    def test_activity_skiplist_allows(self, client):
        r = client.post("/activity", json={
            "url": "https://stackoverflow.com/q/1",
            "title": "Q",
            "domain": "stackoverflow.com",
        })
        assert r.json()["verdict"] == "allow"

    def test_activity_empty_payload(self, client):
        r = client.post("/activity", json={})
        assert r.status_code == 200
        assert r.json()["verdict"] == "allow"


# ---------------------------------------------------------------------------
# Status + stats
# ---------------------------------------------------------------------------


class TestStatusAndStats:
    def test_status_has_all_keys(self, client):
        data = client.get("/status").json()
        assert "current_activity" in data
        assert "active_rules" in data
        assert "blocked" in data

    def test_stats_empty_initially(self, client):
        data = client.get("/stats").json()
        assert data == {"total_activities": 0, "blocked_count": 0}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestConfigFlow:
    def test_set_and_read_gemini_api_key(self, client):
        r = client.post("/config", json={"key": "gemini_api_key", "value": "new-key"})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        v = client.get("/config/gemini_api_key").json()
        assert v["value"] == "new-key"

    def test_set_arbitrary_config(self, client):
        client.post("/config", json={"key": "theme", "value": "dark"})
        assert client.get("/config/theme").json()["value"] == "dark"


# ---------------------------------------------------------------------------
# Habits
# ---------------------------------------------------------------------------


class TestHabitsFlow:
    def test_create_log_and_list_today(self, client):
        r = client.post("/habits", json={"name": "Read", "frequency": "daily", "target": 1})
        assert r.status_code == 200
        hid = r.json()["id"]
        assert hid > 0
        log = client.post(f"/habits/{hid}/log")
        assert log.status_code == 200
        assert log.json()["count"] == 1
        today = client.get("/habits/today").json()
        assert any(h["id"] == hid and h["done"] for h in today)

    def test_habits_today_empty(self, client):
        assert client.get("/habits/today").json() == []

    def test_habit_stats(self, client):
        hid = client.post("/habits", json={"name": "Exercise"}).json()["id"]
        client.post(f"/habits/{hid}/log")
        stats = client.get(f"/habits/{hid}/stats").json()
        assert stats["total_days"] == 1


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------


class TestJournalFlow:
    def test_create_and_list_journal_entry(self, client):
        r = client.post("/journal", json={
            "content": "Productive day.",
            "mood": 8,
            "tags": ["work", "focus"],
        })
        assert r.status_code == 200
        entries = client.get("/journal").json()
        assert len(entries) == 1
        assert entries[0]["content"] == "Productive day."
        assert entries[0]["mood"] == 8
        assert entries[0]["tags"] == ["work", "focus"]

    def test_journal_today(self, client):
        client.post("/journal", json={"content": "Hi", "tags": []})
        today = client.get("/journal/today").json()
        assert today["content"] == "Hi"


# ---------------------------------------------------------------------------
# Commitments
# ---------------------------------------------------------------------------


class TestCommitmentsFlow:
    def test_create_and_list(self, client):
        r = client.post("/commitments", json={
            "text": "Ship e2e tests",
            "deadline": "2099-12-31",
            "stakes": "coffee",
        })
        assert r.status_code == 200
        cid = r.json()["id"]
        assert cid > 0
        lst = client.get("/commitments").json()
        assert any(c["id"] == cid for c in lst)

    def test_commitment_complete(self, client):
        cid = client.post("/commitments", json={
            "text": "Write docs",
            "deadline": "2099-01-01",
        }).json()["id"]
        r = client.post(f"/commitments/{cid}/complete", json={"proof": "done"})
        assert r.json()["ok"] is True
        assert client.get("/commitments").json() == []
        done = client.get("/commitments?status=completed").json()
        assert any(c["id"] == cid for c in done)


# ---------------------------------------------------------------------------
# Journeys
# ---------------------------------------------------------------------------


class TestJourneysFlow:
    def test_create_journey_and_progress(self, client):
        r = client.post("/journeys", json={
            "name": "Learn Rust",
            "description": "Port code to rust",
            "milestones": ["Ownership", "Traits", "Async"],
        })
        assert r.status_code == 200
        jid = r.json()["id"]
        assert jid > 0
        client.post(f"/journeys/{jid}/milestone/0")
        progress = client.get(f"/journeys/{jid}/progress").json()
        assert progress["completed"] == 1
        assert progress["total"] == 3
        assert progress["is_complete"] is False

    def test_list_active_journeys(self, client):
        client.post("/journeys", json={"name": "A", "milestones": ["m1"]})
        out = client.get("/journeys").json()
        assert len(out) == 1


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------


class TestGoalsFlow:
    def test_create_goal(self, client):
        r = client.post("/goals", json={
            "name": "No socials",
            "target_type": "zero",
            "target_value": 0,
            "category": "social",
        })
        assert r.status_code == 200
        assert r.json()["id"] > 0

    def test_goals_list_after_add(self, client):
        client.post("/goals", json={
            "name": "Cap streaming",
            "target_type": "max_seconds",
            "target_value": 600,
            "category": "streaming",
        })
        assert len(client.get("/goals").json()) == 1


# ---------------------------------------------------------------------------
# Challenges
# ---------------------------------------------------------------------------


class TestChallengesFlow:
    def test_create_and_fetch(self, client):
        r = client.post("/challenges", json={
            "name": "Focus 24h",
            "duration_hours": 24,
            "rules": ["no twitter"],
        })
        assert r.status_code == 200
        cid = r.json()["id"]
        assert cid > 0
        ch = client.get(f"/challenges/{cid}").json()
        assert ch["name"] == "Focus 24h"
        assert "seconds_remaining" in ch

    def test_active_challenges(self, client):
        client.post("/challenges", json={
            "name": "X", "duration_hours": 1, "rules": []})
        assert len(client.get("/challenges").json()) == 1


# ---------------------------------------------------------------------------
# Pomodoro + focus
# ---------------------------------------------------------------------------


class TestPomodoroFlow:
    def test_start_and_get_state(self, client):
        r = client.post("/pomodoro/start", json={
            "work_minutes": 25, "break_minutes": 5, "cycles": 4})
        assert r.status_code == 200
        assert r.json()["state"] == "work"
        state = client.get("/pomodoro").json()
        assert state.get("state") == "work"


class TestFocusSessionFlow:
    def test_start_focus_session(self, client):
        r = client.post("/focus/start", json={
            "duration_minutes": 30, "locked": False})
        assert r.status_code == 200
        data = r.json()
        assert data["id"] > 0
        assert data["locked"] is False


# ---------------------------------------------------------------------------
# Achievements + points
# ---------------------------------------------------------------------------


class TestAchievementsFlow:
    def test_list_achievements_has_unlocked_locked(self, client):
        r = client.get("/achievements")
        assert r.status_code == 200
        data = r.json()
        assert "unlocked" in data
        assert "locked" in data

    def test_check_achievements(self, client):
        r = client.post("/achievements/check")
        assert r.status_code == 200
        assert "newly_unlocked" in r.json()


class TestPointsFlow:
    def test_award_and_get_points(self, client):
        r = client.post("/points/award", json={"action": "completed_pomodoro"})
        assert r.status_code == 200
        assert r.json()["total"] == 25
        state = client.get("/points").json()
        assert state["total"] == 25
        # level returned from get_level() is a dict with a "level" field
        assert isinstance(state["level"], dict)
        assert state["level"]["level"] >= 1


# ---------------------------------------------------------------------------
# Mode switching
# ---------------------------------------------------------------------------


class TestModeFlow:
    def test_mode_switch_to_work(self, client):
        r = client.post("/mode/switch", json={"mode": "work"})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["mode"] == "work"
        assert client.get("/mode").json()["mode"] == "work"

    def test_mode_switch_unknown(self, client):
        r = client.post("/mode/switch", json={"mode": "bogus"})
        assert r.status_code == 200
        assert r.json()["ok"] is False


# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------


class TestLimitsFlow:
    def test_create_limit_and_status(self, client):
        r = client.post("/limits", json={
            "category": "social",
            "period": "daily",
            "max_seconds": 1800,
        })
        assert r.status_code == 200
        assert r.json()["id"] > 0
        status = client.get("/limits/status").json()
        assert isinstance(status, list)
        assert len(status) == 1
        assert status[0]["category"] == "social"
        assert status[0]["limit"] == 1800
        assert status[0]["exceeded"] is False


# ---------------------------------------------------------------------------
# Whitelist
# ---------------------------------------------------------------------------


class TestWhitelistFlow:
    def test_add_and_list_whitelist(self, client):
        r = client.post("/whitelist", json={"domain": "wikipedia.org"})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        lst = client.get("/whitelist").json()
        assert "wikipedia.org" in lst["domains"]


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


class TestNotifyFlow:
    def test_notify_macos_mocked(self, client):
        with patch("sentinel.notifications.subprocess.run") as mock_run:
            r = client.post("/notify", json={
                "title": "Hello",
                "message": "World",
                "channels": ["macos"],
            })
        assert r.status_code == 200
        assert r.json()["macos"] is True
        mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealthFlow:
    def test_health_returns_report(self, client):
        with patch("sentinel.health.subprocess.run") as mock_run:
            mock_run.return_value.stdout = ""
            r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        for key in ("api_key_set", "database_healthy", "hosts_writable",
                    "daemon_running", "browser_extension_connected",
                    "rules_count", "uptime_seconds", "issues"):
            assert key in data
        assert data["api_key_set"] is True
        assert data["database_healthy"] is True


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


class TestContextFlow:
    def test_set_get_clear_context(self, client):
        r = client.post("/context", json={"context": "deep work"})
        assert r.status_code == 200
        assert client.get("/context").json()["context"] == "deep work"
        client.delete("/context")
        assert not client.get("/context").json()["context"]


# ---------------------------------------------------------------------------
# Smart
# ---------------------------------------------------------------------------


class TestSmartFlow:
    def test_smart_duplicates_empty(self, client):
        r = client.get("/smart/duplicates")
        assert r.status_code == 200
        assert r.json() == []

    def test_smart_duplicates_with_duplicates(self, client):
        with patch("sentinel.classifier.parse_rule", new_callable=AsyncMock, return_value={}):
            client.post("/rules", json={"text": "Block YouTube"})
            client.post("/rules", json={"text": "Block YouTube"})
        dupes = client.get("/smart/duplicates").json()
        assert len(dupes) == 1


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------


class TestTrackerFlow:
    def test_tracker_start_and_active(self, client):
        r = client.post("/tracker/start", json={
            "project": "sentinel", "description": "tests"})
        assert r.status_code == 200
        assert r.json()["id"] > 0
        active = client.get("/tracker").json()
        assert active["project"] == "sentinel"
        assert active["end_ts"] is None

    def test_tracker_start_stop(self, client):
        client.post("/tracker/start", json={"project": "a"})
        stopped = client.post("/tracker/stop").json()
        assert stopped["end_ts"] is not None
        active = client.get("/tracker").json()
        assert active == {}


# ---------------------------------------------------------------------------
# Full journey integration: multiple endpoints in sequence
# ---------------------------------------------------------------------------


class TestFullJourney:
    def test_kitchen_sink(self, client):
        """Hit a long chain of endpoints in sequence to simulate real use."""
        # 1. configure API key
        client.post("/config", json={"key": "gemini_api_key", "value": "real-key"})
        # 2. create rule
        with patch("sentinel.classifier.parse_rule", new_callable=AsyncMock,
                   return_value={"domains": ["twitter.com"]}):
            rule = client.post("/rules", json={"text": "Block Twitter"}).json()
        assert rule["id"] > 0
        # 3. create habit and log it
        habit = client.post("/habits", json={"name": "Meditate"}).json()
        client.post(f"/habits/{habit['id']}/log")
        # 4. journal entry
        client.post("/journal", json={"content": "Good focus", "mood": 9})
        # 5. commitment
        commit = client.post("/commitments", json={
            "text": "Ship v1",
            "deadline": "2099-12-31",
        }).json()
        assert commit["id"] > 0
        # 6. journey + milestone
        journey = client.post("/journeys", json={
            "name": "Marathon",
            "milestones": ["5k", "10k", "half"],
        }).json()
        client.post(f"/journeys/{journey['id']}/milestone/0")
        # 7. goal
        client.post("/goals", json={
            "name": "No twitter", "target_type": "zero",
            "target_value": 0, "category": "social"})
        # 8. challenge
        client.post("/challenges", json={
            "name": "Dry week", "duration_hours": 168, "rules": []})
        # 9. pomodoro
        client.post("/pomodoro/start", json={"work_minutes": 25})
        # 10. focus
        client.post("/focus/start", json={"duration_minutes": 60, "locked": False})
        # 11. achievements check
        client.post("/achievements/check")
        # 12. award points
        client.post("/points/award", json={"action": "completed_pomodoro"})
        pts = client.get("/points").json()
        assert pts["total"] == 25
        # 13. switch mode
        client.post("/mode/switch", json={"mode": "work"})
        # 14. limit
        client.post("/limits", json={
            "category": "social", "period": "daily", "max_seconds": 1200})
        status = client.get("/limits/status").json()
        assert len(status) == 1
        # 15. whitelist
        client.post("/whitelist", json={"domain": "wikipedia.org"})
        wl = client.get("/whitelist").json()
        assert "wikipedia.org" in wl["domains"]
        # 16. notify (mocked)
        with patch("sentinel.notifications.subprocess.run"):
            client.post("/notify", json={
                "title": "Check", "message": "Hello", "channels": ["macos"]})
        # 17. health
        with patch("sentinel.health.subprocess.run") as mr:
            mr.return_value.stdout = ""
            h = client.get("/health").json()
        assert h["rules_count"] == 1
        # 18. context
        client.post("/context", json={"context": "deep work"})
        assert client.get("/context").json()["context"] == "deep work"
        # 19. smart duplicates
        dupes = client.get("/smart/duplicates").json()
        assert dupes == []
        # 20. tracker
        client.post("/tracker/start", json={"project": "ship"})
        assert client.get("/tracker").json()["project"] == "ship"
        # Final sanity: listings still work
        assert len(client.get("/rules").json()) == 1
        assert len(client.get("/habits").json()) == 1
        assert len(client.get("/journal").json()) == 1
        assert len(client.get("/commitments").json()) == 1
        assert len(client.get("/journeys").json()) == 1
        assert len(client.get("/goals").json()) == 1
