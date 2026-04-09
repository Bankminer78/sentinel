"""Tests for sentinel.db — SQLite database layer (functional API)."""

import json
import time

import pytest

from sentinel import db


# ---------------------------------------------------------------------------
# connect / schema tests
# ---------------------------------------------------------------------------


class TestConnect:
    """Tests for database connection and schema initialization."""

    def test_connect_returns_connection(self, conn):
        assert conn is not None

    def test_connect_creates_rules_table(self, conn):
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rules'"
        ).fetchone()
        assert row is not None

    def test_connect_creates_activity_log_table(self, conn):
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='activity_log'"
        ).fetchone()
        assert row is not None

    def test_connect_creates_seen_domains_table(self, conn):
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='seen_domains'"
        ).fetchone()
        assert row is not None

    def test_connect_creates_config_table(self, conn):
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='config'"
        ).fetchone()
        assert row is not None

    def test_connect_idempotent(self, tmp_path):
        """Calling connect twice on the same path should not raise."""
        p = tmp_path / "test.db"
        c1 = db.connect(p)
        c2 = db.connect(p)
        c1.close()
        c2.close()

    def test_connect_memory_db(self):
        from pathlib import Path
        c = db.connect(Path(":memory:"))
        assert c is not None
        c.close()

    def test_connect_sets_row_factory(self, conn):
        """Rows should be accessible by column name."""
        import sqlite3
        assert conn.row_factory == sqlite3.Row


# ---------------------------------------------------------------------------
# add_rule / get_rules / toggle_rule / delete_rule / update_rule_parsed
# ---------------------------------------------------------------------------


class TestRules:
    """Tests for rule CRUD operations."""

    def test_add_rule_returns_id(self, conn):
        rid = db.add_rule(conn, "Block YouTube")
        assert isinstance(rid, int)
        assert rid > 0

    def test_add_rule_with_parsed(self, conn):
        parsed = {"domains": ["youtube.com"], "action": "block"}
        rid = db.add_rule(conn, "Block YouTube", parsed=parsed)
        rules = db.get_rules(conn, active_only=False)
        found = [r for r in rules if r["id"] == rid][0]
        assert json.loads(found["parsed"]) == parsed

    def test_add_rule_default_parsed_empty(self, conn):
        rid = db.add_rule(conn, "Block Twitter")
        rules = db.get_rules(conn, active_only=False)
        found = [r for r in rules if r["id"] == rid][0]
        assert json.loads(found["parsed"]) == {}

    def test_get_rules_empty(self, conn):
        rules = db.get_rules(conn)
        assert rules == []

    def test_get_rules_returns_list_of_dicts(self, conn):
        db.add_rule(conn, "Rule 1")
        rules = db.get_rules(conn)
        assert isinstance(rules, list)
        assert isinstance(rules[0], dict)

    def test_get_rules_active_only_true(self, conn):
        r1 = db.add_rule(conn, "Active rule")
        r2 = db.add_rule(conn, "Will be toggled")
        db.toggle_rule(conn, r2)
        rules = db.get_rules(conn, active_only=True)
        ids = [r["id"] for r in rules]
        assert r1 in ids
        assert r2 not in ids

    def test_get_rules_active_only_false(self, conn):
        r1 = db.add_rule(conn, "Active rule")
        r2 = db.add_rule(conn, "Will be toggled")
        db.toggle_rule(conn, r2)
        rules = db.get_rules(conn, active_only=False)
        ids = [r["id"] for r in rules]
        assert r1 in ids
        assert r2 in ids

    def test_add_multiple_rules(self, conn):
        db.add_rule(conn, "Rule 1")
        db.add_rule(conn, "Rule 2")
        db.add_rule(conn, "Rule 3")
        rules = db.get_rules(conn, active_only=False)
        assert len(rules) == 3

    def test_toggle_rule_deactivates(self, conn):
        rid = db.add_rule(conn, "Toggle me")
        db.toggle_rule(conn, rid)
        rules = db.get_rules(conn, active_only=False)
        found = [r for r in rules if r["id"] == rid][0]
        assert found["active"] == 0

    def test_toggle_rule_reactivates(self, conn):
        rid = db.add_rule(conn, "Toggle twice")
        db.toggle_rule(conn, rid)
        db.toggle_rule(conn, rid)
        rules = db.get_rules(conn, active_only=False)
        found = [r for r in rules if r["id"] == rid][0]
        assert found["active"] == 1

    def test_delete_rule(self, conn):
        rid = db.add_rule(conn, "Delete me")
        db.delete_rule(conn, rid)
        rules = db.get_rules(conn, active_only=False)
        assert not any(r["id"] == rid for r in rules)

    def test_delete_nonexistent_rule_no_crash(self, conn):
        """Deleting a rule that does not exist should not raise."""
        db.delete_rule(conn, 9999)

    def test_delete_does_not_affect_others(self, conn):
        r1 = db.add_rule(conn, "Keep me")
        r2 = db.add_rule(conn, "Delete me")
        db.delete_rule(conn, r2)
        rules = db.get_rules(conn, active_only=False)
        assert len(rules) == 1
        assert rules[0]["id"] == r1

    def test_update_rule_parsed(self, conn):
        rid = db.add_rule(conn, "Update parsed")
        new_parsed = {"domains": ["reddit.com"], "action": "warn"}
        db.update_rule_parsed(conn, rid, new_parsed)
        rules = db.get_rules(conn, active_only=False)
        found = [r for r in rules if r["id"] == rid][0]
        assert json.loads(found["parsed"]) == new_parsed

    def test_rule_has_default_action_block(self, conn):
        rid = db.add_rule(conn, "Check default action")
        rules = db.get_rules(conn, active_only=False)
        found = [r for r in rules if r["id"] == rid][0]
        assert found["action"] == "block"

    def test_rule_text_preserved(self, conn):
        rid = db.add_rule(conn, "Block Twitter during work hours 9-5")
        rules = db.get_rules(conn, active_only=False)
        found = [r for r in rules if r["id"] == rid][0]
        assert found["text"] == "Block Twitter during work hours 9-5"

    def test_special_characters_in_text(self, conn):
        text = "Block 'quotes' & <html> \"double\" /slashes/ @at #hash"
        rid = db.add_rule(conn, text)
        rules = db.get_rules(conn, active_only=False)
        found = [r for r in rules if r["id"] == rid][0]
        assert found["text"] == text

    def test_unicode_in_text(self, conn):
        text = "Block \u65e5\u672c\u8a9e\u30c6\u30b9\u30c8"
        rid = db.add_rule(conn, text)
        rules = db.get_rules(conn, active_only=False)
        found = [r for r in rules if r["id"] == rid][0]
        assert found["text"] == text


# ---------------------------------------------------------------------------
# log_activity / get_activities
# ---------------------------------------------------------------------------


class TestActivities:
    """Tests for activity logging and retrieval."""

    def test_log_activity_basic(self, conn):
        db.log_activity(conn, "Safari", "Twitter", "https://twitter.com", "twitter.com")
        activities = db.get_activities(conn)
        assert len(activities) == 1

    def test_log_activity_with_verdict(self, conn):
        db.log_activity(conn, "Chrome", "YouTube", "https://youtube.com", "youtube.com",
                        verdict="block", rule_id=1)
        activities = db.get_activities(conn)
        assert activities[0]["verdict"] == "block"
        assert activities[0]["rule_id"] == 1

    def test_get_activities_returns_list_of_dicts(self, conn):
        db.log_activity(conn, "Safari", "Google", "https://google.com", "google.com")
        activities = db.get_activities(conn)
        assert isinstance(activities, list)
        assert isinstance(activities[0], dict)

    def test_get_activities_empty(self, conn):
        activities = db.get_activities(conn)
        assert activities == []

    def test_get_activities_limit(self, conn):
        for i in range(10):
            db.log_activity(conn, f"App{i}", f"Title{i}", f"https://site{i}.com", f"site{i}.com")
        activities = db.get_activities(conn, limit=3)
        assert len(activities) == 3

    def test_get_activities_default_limit_100(self, conn):
        for i in range(5):
            db.log_activity(conn, f"App{i}", f"Title{i}", "", "")
        activities = db.get_activities(conn)
        assert len(activities) == 5

    def test_get_activities_since(self, conn):
        cutoff = time.time()
        time.sleep(0.01)
        db.log_activity(conn, "After", "After", "", "after.com")
        activities = db.get_activities(conn, since=cutoff)
        assert len(activities) == 1
        assert activities[0]["domain"] == "after.com"

    def test_get_activities_since_filters_old(self, conn):
        db.log_activity(conn, "Old", "Old", "", "old.com")
        cutoff = time.time() + 10
        activities = db.get_activities(conn, since=cutoff)
        assert len(activities) == 0

    def test_get_activities_ordered_desc(self, conn):
        db.log_activity(conn, "First", "First", "", "first.com")
        time.sleep(0.01)
        db.log_activity(conn, "Second", "Second", "", "second.com")
        activities = db.get_activities(conn)
        assert activities[0]["app"] == "Second"
        assert activities[1]["app"] == "First"

    def test_log_activity_preserves_fields(self, conn):
        db.log_activity(conn, "Safari", "GitHub", "https://github.com/user", "github.com",
                        verdict="allow", rule_id=42)
        a = db.get_activities(conn)[0]
        assert a["app"] == "Safari"
        assert a["title"] == "GitHub"
        assert a["url"] == "https://github.com/user"
        assert a["domain"] == "github.com"
        assert a["verdict"] == "allow"
        assert a["rule_id"] == 42

    def test_log_activity_sets_timestamp(self, conn):
        before = time.time()
        db.log_activity(conn, "App", "Title", "", "")
        after = time.time()
        a = db.get_activities(conn)[0]
        assert before <= a["ts"] <= after

    def test_very_long_url(self, conn):
        long_url = "https://example.com/" + "a" * 5000
        db.log_activity(conn, "Safari", "Long URL", long_url, "example.com")
        activities = db.get_activities(conn)
        assert len(activities) == 1

    def test_unicode_in_title(self, conn):
        db.log_activity(conn, "Safari", "\u65e5\u672c\u8a9e\u30c6\u30b9\u30c8", "", "")
        a = db.get_activities(conn)[0]
        assert a["title"] == "\u65e5\u672c\u8a9e\u30c6\u30b9\u30c8"


# ---------------------------------------------------------------------------
# save_seen / get_seen
# ---------------------------------------------------------------------------


class TestSeenDomains:
    """Tests for the seen domain cache."""

    def test_get_seen_unknown_returns_none(self, conn):
        assert db.get_seen(conn, "never-seen.com") is None

    def test_save_and_get_seen(self, conn):
        db.save_seen(conn, "twitter.com", "social")
        assert db.get_seen(conn, "twitter.com") == "social"

    def test_save_seen_overwrites(self, conn):
        db.save_seen(conn, "reddit.com", "none")
        db.save_seen(conn, "reddit.com", "social")
        assert db.get_seen(conn, "reddit.com") == "social"

    def test_save_multiple_domains(self, conn):
        db.save_seen(conn, "twitter.com", "social")
        db.save_seen(conn, "github.com", "none")
        db.save_seen(conn, "youtube.com", "streaming")
        assert db.get_seen(conn, "twitter.com") == "social"
        assert db.get_seen(conn, "github.com") == "none"
        assert db.get_seen(conn, "youtube.com") == "streaming"

    def test_save_seen_category_none_string(self, conn):
        db.save_seen(conn, "docs.python.org", "none")
        assert db.get_seen(conn, "docs.python.org") == "none"

    def test_get_seen_returns_string(self, conn):
        db.save_seen(conn, "test.com", "gaming")
        result = db.get_seen(conn, "test.com")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# get_config / set_config
# ---------------------------------------------------------------------------


class TestConfig:
    """Tests for the config key-value store."""

    def test_get_config_missing_returns_default(self, conn):
        assert db.get_config(conn, "missing") is None

    def test_get_config_missing_custom_default(self, conn):
        assert db.get_config(conn, "missing", default="fallback") == "fallback"

    def test_set_and_get_config(self, conn):
        db.set_config(conn, "gemini_api_key", "test-key-123")
        assert db.get_config(conn, "gemini_api_key") == "test-key-123"

    def test_set_config_overwrites(self, conn):
        db.set_config(conn, "key", "old")
        db.set_config(conn, "key", "new")
        assert db.get_config(conn, "key") == "new"

    def test_set_multiple_configs(self, conn):
        db.set_config(conn, "key1", "val1")
        db.set_config(conn, "key2", "val2")
        assert db.get_config(conn, "key1") == "val1"
        assert db.get_config(conn, "key2") == "val2"

    def test_config_stores_string_values(self, conn):
        db.set_config(conn, "number", "42")
        assert db.get_config(conn, "number") == "42"

    def test_config_empty_value(self, conn):
        db.set_config(conn, "empty", "")
        assert db.get_config(conn, "empty") == ""
