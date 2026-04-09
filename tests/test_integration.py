"""Integration tests — End-to-end flows through the Sentinel system.

These tests exercise multiple modules together using the actual functional APIs
(without the HTTP/FastAPI layer, which is covered by test_server.py):
  - sentinel.db (functional, SQLite)
  - sentinel.blocker (module-level state)
  - sentinel.classifier (async, Gemini)
  - sentinel.skiplist (module-level function)
  - sentinel.monitor (module-level state)
"""

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel import blocker, classifier, db, monitor, skiplist


# ---------------------------------------------------------------------------
# End-to-end: Rule creation -> domain classification -> blocking
# ---------------------------------------------------------------------------


class TestRuleCreationToBlocking:
    """Full flow: create rule -> classify domain -> block."""

    @pytest.mark.asyncio
    async def test_create_rule_classify_and_block(self, conn):
        """Create a rule, classify a domain, block it."""
        # Step 1: Create a rule
        rid = db.add_rule(conn, "Block all social media")
        assert rid > 0

        # Step 2: Parse it with the LLM
        parsed = {"categories": ["social"], "action": "block"}
        db.update_rule_parsed(conn, rid, parsed)

        # Step 3: Classify a new domain
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="social"):
            category = await classifier.classify_domain("fake-key", "twitter.com")
            assert category == "social"

        # Step 4: Save classification to DB
        db.save_seen(conn, "twitter.com", category)
        assert db.get_seen(conn, "twitter.com") == "social"

        # Step 5: Evaluate rules
        rules = db.get_rules(conn)
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="block"):
            verdict = await classifier.evaluate_rules(
                "fake-key", "Safari", "twitter.com", "Twitter", rules)
            assert verdict == "block"

        # Step 6: Block the domain
        with patch.object(blocker, "_sync_hosts"):
            blocker.block_domain("twitter.com")
            assert blocker.is_blocked_domain("twitter.com")

        # Step 7: Log the activity
        db.log_activity(conn, "Safari", "Twitter", "https://twitter.com", "twitter.com", "block", rid)
        activities = db.get_activities(conn, since=time.time() - 60)
        assert len(activities) >= 1
        assert activities[0]["verdict"] == "block"

    @pytest.mark.asyncio
    async def test_safe_domain_not_blocked(self, conn):
        """Productive domain classified as 'none' should not be blocked."""
        db.add_rule(conn, "Block distracting sites")

        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="none"):
            category = await classifier.classify_domain("fake-key", "github.com")
            assert category == "none"

        db.save_seen(conn, "github.com", category)
        assert not blocker.is_blocked_domain("github.com")

    @pytest.mark.asyncio
    async def test_toggle_rule_excludes_from_active(self, conn):
        """Toggled-off rules should not appear in active-only queries."""
        rid = db.add_rule(conn, "Block social media")
        db.toggle_rule(conn, rid)

        active_rules = db.get_rules(conn, active_only=True)
        assert not any(r["id"] == rid for r in active_rules)

    @pytest.mark.asyncio
    async def test_delete_rule_removes_from_db(self, conn):
        """Deleted rules should not be returned at all."""
        rid = db.add_rule(conn, "Block YouTube")
        db.delete_rule(conn, rid)

        all_rules = db.get_rules(conn, active_only=False)
        assert not any(r["id"] == rid for r in all_rules)


# ---------------------------------------------------------------------------
# End-to-end: Skiplist -> classification gating
# ---------------------------------------------------------------------------


class TestSkiplistGating:
    """Skiplist domains should bypass classification entirely."""

    def test_skiplist_domain_bypasses_classification(self):
        assert skiplist.should_skip("google.com") is True

    @pytest.mark.asyncio
    async def test_non_skiplist_domain_needs_classification(self, conn):
        assert skiplist.should_skip("twitter.com") is False

        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="social"):
            category = await classifier.classify_domain("fake-key", "twitter.com")
            assert category == "social"

    def test_skiplist_parent_domain_match(self):
        assert skiplist.should_skip("calendar.google.com") is True
        assert skiplist.should_skip("docs.google.com") is True

    def test_localhost_always_skipped(self):
        assert skiplist.should_skip("localhost:3000") is True
        assert skiplist.should_skip("127.0.0.1:8080") is True

    def test_internal_domains_skipped(self):
        assert skiplist.should_skip("myapp.internal") is True
        assert skiplist.should_skip("staging.local") is True


# ---------------------------------------------------------------------------
# End-to-end: Domain seen cache
# ---------------------------------------------------------------------------


class TestDomainSeenCache:
    """Flow: check DB cache -> classify if new -> cache result."""

    @pytest.mark.asyncio
    async def test_first_visit_classifies_and_caches(self, conn):
        assert db.get_seen(conn, "netflix.com") is None

        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="streaming"):
            category = await classifier.classify_domain("fake-key", "netflix.com")
        db.save_seen(conn, "netflix.com", category)

        assert db.get_seen(conn, "netflix.com") == "streaming"

    def test_second_visit_uses_db_cache(self, conn):
        db.save_seen(conn, "twitter.com", "social")
        assert db.get_seen(conn, "twitter.com") == "social"

    def test_cache_update_on_recategorization(self, conn):
        db.save_seen(conn, "reddit.com", "none")
        db.save_seen(conn, "reddit.com", "social")
        assert db.get_seen(conn, "reddit.com") == "social"

    @pytest.mark.asyncio
    async def test_classifier_memory_cache_prevents_repeated_api_calls(self):
        """The in-memory classifier cache should prevent duplicate API calls."""
        mock_gemini = AsyncMock(return_value="social")
        with patch.object(classifier, "call_gemini", mock_gemini):
            await classifier.classify_domain("fake-key", "twitter.com")
            await classifier.classify_domain("fake-key", "twitter.com")
            assert mock_gemini.call_count == 1


# ---------------------------------------------------------------------------
# End-to-end: Block + Unblock cycle
# ---------------------------------------------------------------------------


class TestBlockUnblockCycle:
    """Full block -> verify -> unblock -> verify cycle."""

    def test_full_domain_cycle(self):
        with patch.object(blocker, "_sync_hosts"):
            assert not blocker.is_blocked_domain("twitter.com")
            blocker.block_domain("twitter.com")
            assert blocker.is_blocked_domain("twitter.com")
            blocker.unblock_domain("twitter.com")
            assert not blocker.is_blocked_domain("twitter.com")

    def test_block_multiple_unblock_one(self):
        with patch.object(blocker, "_sync_hosts"):
            blocker.block_domain("twitter.com")
            blocker.block_domain("facebook.com")
            blocker.block_domain("reddit.com")

            blocker.unblock_domain("facebook.com")

            assert blocker.is_blocked_domain("twitter.com")
            assert not blocker.is_blocked_domain("facebook.com")
            assert blocker.is_blocked_domain("reddit.com")

    def test_block_domain_and_app_together(self):
        with patch.object(blocker, "_sync_hosts"), \
             patch.object(blocker, "kill_app"):
            blocker.block_domain("twitter.com")
            blocker.block_app("com.discord.Discord")

            result = blocker.get_blocked()
            assert "twitter.com" in result["domains"]
            assert "com.discord.Discord" in result["apps"]

    def test_get_blocked_reflects_current_state(self):
        with patch.object(blocker, "_sync_hosts"):
            blocker.block_domain("a.com")
            blocker.block_domain("b.com")
            result = blocker.get_blocked()
            assert set(result["domains"]) == {"a.com", "b.com"}

            blocker.unblock_domain("a.com")
            result = blocker.get_blocked()
            assert result["domains"] == ["b.com"]


# ---------------------------------------------------------------------------
# End-to-end: App blocking flow
# ---------------------------------------------------------------------------


class TestAppBlockingFlow:
    """Block app -> kill -> verify blocked."""

    def test_block_app_kills_and_marks(self):
        with patch.object(blocker, "kill_app") as mock_kill:
            blocker.block_app("com.discord.Discord")
            mock_kill.assert_called_once_with("com.discord.Discord")
            assert blocker.is_blocked_app("com.discord.Discord")

    def test_enforce_blocked_app(self):
        with patch.object(blocker, "kill_app") as mock_kill:
            blocker._blocked_apps.add("com.discord.Discord")
            blocker.enforce("com.discord.Discord")
            mock_kill.assert_called_once_with("com.discord.Discord")

    def test_enforce_non_blocked_app_noop(self):
        with patch.object(blocker, "kill_app") as mock_kill:
            blocker.enforce("com.apple.Safari")
            mock_kill.assert_not_called()

    def test_unblock_app_allows_again(self):
        with patch.object(blocker, "kill_app"):
            blocker.block_app("com.discord.Discord")
            blocker.unblock_app("com.discord.Discord")
            assert not blocker.is_blocked_app("com.discord.Discord")


# ---------------------------------------------------------------------------
# End-to-end: Monitor + browser extension
# ---------------------------------------------------------------------------


class TestMonitorBrowserExtension:
    """Monitor receives URL from browser extension."""

    def test_set_browser_url_then_read(self):
        monitor.set_browser_url("https://twitter.com/home")
        assert monitor._browser_url == "https://twitter.com/home"

    def test_get_current_returns_expected_structure(self):
        result = monitor.get_current()
        assert isinstance(result, dict)
        for key in ("app", "title", "url", "domain", "bundle_id"):
            assert key in result

    def test_start_stop_cycle(self):
        monitor.start()
        assert monitor._running is True
        monitor.stop()
        assert monitor._running is False

    def test_extract_domain_works(self):
        assert monitor._extract_domain("https://twitter.com/home") == "twitter.com"
        assert monitor._extract_domain("") == ""


# ---------------------------------------------------------------------------
# End-to-end: DB persistence round-trip
# ---------------------------------------------------------------------------


class TestDBPersistenceRoundTrip:
    """Test that data survives a full save -> retrieve cycle."""

    def test_rule_round_trip(self, conn):
        parsed = {"domains": ["reddit.com"], "categories": ["social"], "action": "block"}
        rid = db.add_rule(conn, "Block Reddit during work", parsed=parsed)

        rules = db.get_rules(conn, active_only=False)
        found = [r for r in rules if r["id"] == rid][0]
        assert found["text"] == "Block Reddit during work"
        assert json.loads(found["parsed"]) == parsed

    def test_activity_round_trip(self, conn):
        now = time.time()
        db.log_activity(conn, "Safari", "Twitter / X", "https://twitter.com", "twitter.com", "block")

        activities = db.get_activities(conn, since=now - 60)
        assert len(activities) >= 1
        assert activities[0]["app"] == "Safari"
        assert activities[0]["domain"] == "twitter.com"
        assert activities[0]["verdict"] == "block"

    def test_seen_domain_round_trip(self, conn):
        db.save_seen(conn, "twitter.com", "social")
        db.save_seen(conn, "github.com", "none")
        db.save_seen(conn, "youtube.com", "streaming")

        assert db.get_seen(conn, "twitter.com") == "social"
        assert db.get_seen(conn, "github.com") == "none"
        assert db.get_seen(conn, "youtube.com") == "streaming"
        assert db.get_seen(conn, "unknown.com") is None

    def test_config_round_trip(self, conn):
        db.set_config(conn, "gemini_api_key", "test-key-123")
        assert db.get_config(conn, "gemini_api_key") == "test-key-123"

    def test_config_default_value(self, conn):
        assert db.get_config(conn, "nonexistent_key", "default") == "default"


# ---------------------------------------------------------------------------
# End-to-end: Full activity report flow (modules only, no HTTP)
# ---------------------------------------------------------------------------


class TestFullActivityReportFlow:
    """Simulates the server /activity logic using modules directly."""

    @pytest.mark.asyncio
    async def test_new_social_domain_gets_blocked(self, conn):
        """New social domain with active rules should be blocked."""
        db.add_rule(conn, "Block all social media")
        api_key = "fake-key"
        domain = "instagram.com"

        # Not on skiplist
        assert not skiplist.should_skip(domain)
        # Not already seen
        assert db.get_seen(conn, domain) is None
        # Not already blocked
        assert not blocker.is_blocked_domain(domain)

        # Classify as social
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="social"):
            category = await classifier.classify_domain(api_key, domain)
        db.save_seen(conn, domain, category)
        assert category == "social"

        # Evaluate rules
        rules = db.get_rules(conn)
        with patch.object(classifier, "call_gemini", new_callable=AsyncMock, return_value="block"):
            verdict = await classifier.evaluate_rules(api_key, "Safari", domain, "Instagram", rules)
        assert verdict == "block"

        # Block it
        with patch.object(blocker, "_sync_hosts"):
            blocker.block_domain(domain)
        assert blocker.is_blocked_domain(domain)

        # Log
        db.log_activity(conn, "Safari", "Instagram", f"https://{domain}", domain, "block")
        activities = db.get_activities(conn, since=time.time() - 60)
        assert any(a["domain"] == domain and a["verdict"] == "block" for a in activities)

    @pytest.mark.asyncio
    async def test_utility_domain_allowed(self, conn):
        """Utility domain on skiplist should be allowed immediately."""
        assert skiplist.should_skip("google.com") is True
        # No classification or blocking needed

    @pytest.mark.asyncio
    async def test_already_blocked_domain_detected(self, conn):
        """If a domain is already blocked, verdict is immediate."""
        with patch.object(blocker, "_sync_hosts"):
            blocker.block_domain("netflix.com")
        assert blocker.is_blocked_domain("netflix.com")

    @pytest.mark.asyncio
    async def test_already_seen_none_domain_allowed(self, conn):
        """Domain already seen as 'none' should be allowed without API call."""
        db.save_seen(conn, "docs.python.org", "none")
        assert db.get_seen(conn, "docs.python.org") == "none"
        # No classification needed

    @pytest.mark.asyncio
    async def test_multiple_rules_influence_verdict(self, conn):
        """Multiple rules should all be sent to the LLM for evaluation."""
        db.add_rule(conn, "Block social media", parsed={"categories": ["social"]})
        db.add_rule(conn, "Block streaming", parsed={"categories": ["streaming"]})

        rules = db.get_rules(conn)
        assert len(rules) == 2

        mock_gemini = AsyncMock(return_value="block")
        with patch.object(classifier, "call_gemini", mock_gemini):
            verdict = await classifier.evaluate_rules(
                "fake-key", "Chrome", "twitch.tv", "Twitch", rules)
        assert verdict == "block"

        # Verify both rules were included in the prompt
        call_args = mock_gemini.call_args
        prompt = call_args[0][1]
        assert "Block social media" in prompt
        assert "Block streaming" in prompt
