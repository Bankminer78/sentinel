"""Integration tests for the FastAPI server."""

import sqlite3

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from pathlib import Path

from sentinel.server import app
from sentinel import db, blocker, monitor


def _make_test_conn():
    """Create an in-memory SQLite connection that allows multi-threaded access."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
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
    """)
    return conn


@pytest.fixture
def client():
    """Test client with in-memory DB, startup event bypassed."""
    import sentinel.server as srv

    c = _make_test_conn()
    db.set_config(c, "gemini_api_key", "test-key")
    # Pre-set the conn so startup doesn't overwrite it, and patch startup
    srv.conn = c
    with patch.object(blocker, "_sync_hosts"), \
         patch("sentinel.server.startup"), \
         patch.object(monitor, "start"):
        with TestClient(app, raise_server_exceptions=True) as tc:
            # Ensure conn is still our test connection (startup may have run)
            srv.conn = c
            yield tc
    c.close()
    srv.conn = None


# ---------------------------------------------------------------------------
# Rules endpoints
# ---------------------------------------------------------------------------


class TestRulesEndpoints:
    """Tests for /rules CRUD endpoints."""

    def test_create_rule(self, client):
        with patch("sentinel.classifier.parse_rule", new_callable=AsyncMock,
                   return_value={"domains": ["youtube.com"], "action": "block"}):
            r = client.post("/rules", json={"text": "Block YouTube"})
        assert r.status_code == 200
        data = r.json()
        assert data["text"] == "Block YouTube"
        assert data["id"] is not None
        assert isinstance(data["parsed"], dict)

    def test_create_rule_without_api_key(self):
        """When no api key configured, parsed should be empty."""
        import sentinel.server as srv
        c = _make_test_conn()
        srv.conn = c
        with patch.object(blocker, "_sync_hosts"), \
             patch("sentinel.server.startup"), \
             patch.object(monitor, "start"):
            with TestClient(app) as tc:
                srv.conn = c
                r = tc.post("/rules", json={"text": "Block YouTube"})
        assert r.status_code == 200
        assert r.json()["parsed"] == {}
        c.close()
        srv.conn = None

    def test_list_rules(self, client):
        with patch("sentinel.classifier.parse_rule", new_callable=AsyncMock, return_value={}):
            client.post("/rules", json={"text": "Rule 1"})
            client.post("/rules", json={"text": "Rule 2"})
        r = client.get("/rules")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_list_rules_empty(self, client):
        r = client.get("/rules")
        assert r.status_code == 200
        assert r.json() == []

    def test_delete_rule(self, client):
        with patch("sentinel.classifier.parse_rule", new_callable=AsyncMock, return_value={}):
            create = client.post("/rules", json={"text": "Temporary"})
        rid = create.json()["id"]
        r = client.delete(f"/rules/{rid}")
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert len(client.get("/rules").json()) == 0

    def test_toggle_rule(self, client):
        with patch("sentinel.classifier.parse_rule", new_callable=AsyncMock, return_value={}):
            create = client.post("/rules", json={"text": "Toggle me"})
        rid = create.json()["id"]
        r = client.post(f"/rules/{rid}/toggle")
        assert r.status_code == 200
        rules = client.get("/rules").json()
        assert any(rule["active"] == 0 for rule in rules)

    def test_toggle_rule_twice_reactivates(self, client):
        with patch("sentinel.classifier.parse_rule", new_callable=AsyncMock, return_value={}):
            create = client.post("/rules", json={"text": "Toggle twice"})
        rid = create.json()["id"]
        client.post(f"/rules/{rid}/toggle")
        client.post(f"/rules/{rid}/toggle")
        rules = client.get("/rules").json()
        toggled = [r for r in rules if r["id"] == rid][0]
        assert toggled["active"] == 1


# ---------------------------------------------------------------------------
# Status and stats endpoints
# ---------------------------------------------------------------------------


class TestStatusStats:
    """Tests for /status and /stats endpoints."""

    def test_status(self, client):
        r = client.get("/status")
        assert r.status_code == 200
        data = r.json()
        assert "current_activity" in data
        assert "active_rules" in data
        assert "blocked" in data

    def test_status_current_activity_has_keys(self, client):
        r = client.get("/status")
        activity = r.json()["current_activity"]
        assert "app" in activity
        assert "title" in activity
        assert "url" in activity
        assert "domain" in activity

    def test_stats(self, client):
        r = client.get("/stats")
        assert r.status_code == 200
        data = r.json()
        assert "total_activities" in data
        assert "blocked_count" in data

    def test_stats_empty(self, client):
        r = client.get("/stats")
        assert r.json()["total_activities"] == 0
        assert r.json()["blocked_count"] == 0


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------


class TestConfigEndpoints:
    """Tests for /config endpoints."""

    def test_set_config(self, client):
        r = client.post("/config", json={"key": "test_key", "value": "test_value"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_get_config(self, client):
        client.post("/config", json={"key": "my_key", "value": "my_val"})
        r = client.get("/config/my_key")
        assert r.status_code == 200
        assert r.json()["value"] == "my_val"

    def test_get_config_missing(self, client):
        r = client.get("/config/nonexistent")
        assert r.status_code == 200
        assert r.json()["value"] is None

    def test_set_config_overwrite(self, client):
        client.post("/config", json={"key": "k", "value": "old"})
        client.post("/config", json={"key": "k", "value": "new"})
        r = client.get("/config/k")
        assert r.json()["value"] == "new"


# ---------------------------------------------------------------------------
# Block endpoints
# ---------------------------------------------------------------------------


class TestBlockEndpoints:
    """Tests for /block/domain endpoints."""

    def test_manual_block_domain(self, client):
        r = client.post("/block/domain/youtube.com")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_manual_unblock_domain(self, client):
        client.post("/block/domain/youtube.com")
        r = client.delete("/block/domain/youtube.com")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_blocked_domain_shows_in_status(self, client):
        client.post("/block/domain/twitter.com")
        r = client.get("/status")
        blocked = r.json()["blocked"]
        assert "twitter.com" in blocked["domains"]

    def test_unblocked_domain_removed_from_status(self, client):
        client.post("/block/domain/twitter.com")
        client.delete("/block/domain/twitter.com")
        r = client.get("/status")
        blocked = r.json()["blocked"]
        assert "twitter.com" not in blocked["domains"]


# ---------------------------------------------------------------------------
# Activity endpoint
# ---------------------------------------------------------------------------


class TestActivityEndpoint:
    """Tests for POST /activity."""

    def test_activity_skip_utility_domain(self, client):
        r = client.post("/activity", json={
            "url": "https://github.com",
            "title": "GitHub",
            "domain": "github.com",
        })
        assert r.json()["verdict"] == "allow"

    def test_activity_empty_domain(self, client):
        r = client.post("/activity", json={"url": "", "title": "", "domain": ""})
        assert r.json()["verdict"] == "allow"

    def test_activity_no_api_key_allows(self):
        """Without an API key, all activity is allowed."""
        import sentinel.server as srv
        c = _make_test_conn()
        srv.conn = c
        with patch.object(blocker, "_sync_hosts"), \
             patch("sentinel.server.startup"), \
             patch.object(monitor, "start"):
            with TestClient(app) as tc:
                srv.conn = c
                r = tc.post("/activity", json={
                    "url": "https://twitter.com",
                    "title": "Twitter",
                    "domain": "twitter.com",
                })
        assert r.json()["verdict"] == "allow"
        c.close()
        srv.conn = None

    def test_activity_blocked_domain_returns_block(self, client):
        blocker._blocked_domains.add("netflix.com")
        r = client.post("/activity", json={
            "url": "https://netflix.com",
            "domain": "netflix.com",
            "title": "Netflix",
        })
        assert r.json()["verdict"] == "block"

    def test_activity_seen_none_allows(self, client):
        """A domain already seen as 'none' should be allowed."""
        import sentinel.server as srv
        db.save_seen(srv.conn, "productive.com", "none")
        r = client.post("/activity", json={
            "url": "https://productive.com",
            "domain": "productive.com",
            "title": "Productive",
        })
        assert r.json()["verdict"] == "allow"

    def test_activity_seen_approved_allows(self, client):
        """A domain already seen as 'approved' should be allowed."""
        import sentinel.server as srv
        db.save_seen(srv.conn, "approved.com", "approved")
        r = client.post("/activity", json={
            "url": "https://approved.com",
            "domain": "approved.com",
            "title": "Approved",
        })
        assert r.json()["verdict"] == "allow"

    def test_activity_unseen_domain_classifies(self, client):
        """An unseen domain triggers classification."""
        with patch("sentinel.classifier.classify_domain", new_callable=AsyncMock, return_value="none"):
            r = client.post("/activity", json={
                "url": "https://new-site.com",
                "domain": "new-site.com",
                "title": "New Site",
            })
        assert r.json()["verdict"] == "allow"


# ---------------------------------------------------------------------------
# Pomodoro endpoints
# ---------------------------------------------------------------------------


class TestPomodoroEndpoints:
    """Tests for /pomodoro endpoints."""

    def test_pomodoro_start(self, client):
        r = client.post("/pomodoro/start", json={"work_minutes": 25, "break_minutes": 5, "cycles": 4})
        assert r.status_code == 200
        data = r.json()
        assert "id" in data
        assert data["state"] == "work"

    def test_pomodoro_state_after_start(self, client):
        client.post("/pomodoro/start", json={"work_minutes": 25, "break_minutes": 5, "cycles": 4})
        r = client.get("/pomodoro")
        assert r.status_code == 200
        data = r.json()
        assert data.get("state") == "work"

    def test_pomodoro_stop(self, client):
        client.post("/pomodoro/start", json={"work_minutes": 25, "break_minutes": 5, "cycles": 4})
        r = client.delete("/pomodoro")
        assert r.status_code == 200
        assert r.json()["ok"] is True
        # After stop, state should be empty
        r2 = client.get("/pomodoro")
        assert r2.json() == {}

    def test_pomodoro_empty_when_none(self, client):
        r = client.get("/pomodoro")
        assert r.status_code == 200
        assert r.json() == {}


# ---------------------------------------------------------------------------
# Focus session endpoints
# ---------------------------------------------------------------------------


class TestFocusEndpoints:
    """Tests for /focus endpoints."""

    def test_focus_start(self, client):
        r = client.post("/focus/start", json={"duration_minutes": 60, "locked": False})
        assert r.status_code == 200
        data = r.json()
        assert "id" in data
        assert data["locked"] is False

    def test_focus_status(self, client):
        client.post("/focus/start", json={"duration_minutes": 60, "locked": False})
        r = client.get("/focus")
        assert r.status_code == 200
        assert r.json().get("locked") is False

    def test_focus_end_unlocked(self, client):
        start = client.post("/focus/start", json={"duration_minutes": 60, "locked": False}).json()
        sid = start["id"]
        r = client.delete(f"/focus/{sid}?force=false")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_focus_end_locked_requires_force(self, client):
        start = client.post("/focus/start", json={"duration_minutes": 60, "locked": True}).json()
        sid = start["id"]
        r = client.delete(f"/focus/{sid}?force=false")
        assert r.json()["ok"] is False


# ---------------------------------------------------------------------------
# Intervention endpoints
# ---------------------------------------------------------------------------


class TestInterventionEndpoints:
    """Tests for /intervention endpoints."""

    def test_intervention_create(self, client):
        r = client.post("/intervention", json={"kind": "math", "context": {}})
        assert r.status_code == 200
        data = r.json()
        assert "id" in data
        assert data["kind"] == "math"
        assert "prompt" in data

    def test_intervention_create_invalid_kind(self, client):
        r = client.post("/intervention", json={"kind": "nonexistent", "context": {}})
        assert r.status_code == 400

    def test_intervention_get(self, client):
        create = client.post("/intervention", json={"kind": "typing", "context": {}}).json()
        r = client.get(f"/intervention/{create['id']}")
        assert r.status_code == 200
        assert r.json()["kind"] == "typing"

    def test_intervention_get_missing(self, client):
        r = client.get("/intervention/9999")
        assert r.status_code == 404

    def test_intervention_submit_typing_wrong(self, client):
        create = client.post("/intervention", json={"kind": "typing", "context": {}}).json()
        r = client.post(f"/intervention/{create['id']}/submit", json={"response": "wrong answer"})
        assert r.status_code == 200
        assert r.json()["passed"] is False

    def test_intervention_submit_typing_correct(self, client):
        create = client.post("/intervention", json={"kind": "typing", "context": {}}).json()
        phrase = create["state"]["phrase"]
        r = client.post(f"/intervention/{create['id']}/submit", json={"response": phrase})
        assert r.json()["passed"] is True


# ---------------------------------------------------------------------------
# Stats endpoints (new)
# ---------------------------------------------------------------------------


class TestStatsEndpoints:
    """Tests for /stats/* endpoints."""

    def test_stats_score(self, client):
        r = client.get("/stats/score")
        assert r.status_code == 200
        assert "score" in r.json()

    def test_stats_breakdown(self, client):
        r = client.get("/stats/breakdown")
        assert r.status_code == 200
        data = r.json()
        assert "productive" in data
        assert "distracting" in data

    def test_stats_top_distractions(self, client):
        r = client.get("/stats/top-distractions?days=7")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_stats_week(self, client):
        r = client.get("/stats/week")
        assert r.status_code == 200
        assert r.json()["days"] == 7

    def test_stats_month(self, client):
        r = client.get("/stats/month")
        assert r.status_code == 200
        assert r.json()["days"] == 30


# ---------------------------------------------------------------------------
# Goals endpoints
# ---------------------------------------------------------------------------


class TestGoalsEndpoints:
    """Tests for /goals endpoints."""

    def test_goal_add(self, client):
        r = client.post("/goals", json={
            "name": "No social",
            "target_type": "max_seconds",
            "target_value": 1800,
            "category": "social",
        })
        assert r.status_code == 200
        assert "id" in r.json()

    def test_goal_list(self, client):
        client.post("/goals", json={
            "name": "G1", "target_type": "zero", "target_value": 0, "category": "social"})
        client.post("/goals", json={
            "name": "G2", "target_type": "max_seconds", "target_value": 600, "category": None})
        r = client.get("/goals")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_goal_remove(self, client):
        gid = client.post("/goals", json={
            "name": "Temp", "target_type": "zero", "target_value": 0, "category": None}).json()["id"]
        r = client.delete(f"/goals/{gid}")
        assert r.status_code == 200
        assert len(client.get("/goals").json()) == 0

    def test_goal_progress(self, client):
        gid = client.post("/goals", json={
            "name": "Social cap", "target_type": "max_seconds",
            "target_value": 1800, "category": "social"}).json()["id"]
        r = client.get(f"/goals/{gid}/progress")
        assert r.status_code == 200
        data = r.json()
        assert data["goal_id"] == gid
        assert "met" in data

    def test_goal_progress_missing(self, client):
        r = client.get("/goals/9999/progress")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Activity decision endpoint
# ---------------------------------------------------------------------------


class TestActivityDecisionEndpoint:
    """Tests for POST /activity/decision."""

    def test_activity_decision_confirmed(self, client):
        r = client.post("/activity/decision", json={
            "url": "https://twitter.com/home",
            "decision": "confirmed",
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_activity_decision_cancelled(self, client):
        r = client.post("/activity/decision", json={
            "url": "https://youtube.com/",
            "decision": "cancelled",
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True
