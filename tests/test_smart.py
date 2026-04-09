"""Tests for sentinel.smart."""
import pytest
import json
from unittest.mock import patch, AsyncMock
from sentinel import smart, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_find_duplicates_empty(conn):
    assert smart.find_duplicates(conn) == []


def test_find_duplicates_single(conn):
    db.add_rule(conn, "Block YouTube")
    assert smart.find_duplicates(conn) == []


def test_find_duplicates_exact(conn):
    db.add_rule(conn, "Block YouTube")
    db.add_rule(conn, "Block YouTube")
    dupes = smart.find_duplicates(conn)
    assert len(dupes) == 1


def test_find_duplicates_case_insensitive(conn):
    db.add_rule(conn, "block youtube")
    db.add_rule(conn, "BLOCK YOUTUBE")
    assert len(smart.find_duplicates(conn)) == 1


def test_find_conflicts_empty(conn):
    assert smart.find_conflicts(conn) == []


def test_find_conflicts_single_domain(conn):
    db.add_rule(conn, "Block YouTube", {"domains": ["youtube.com"]})
    assert smart.find_conflicts(conn) == []


def test_find_conflicts_multiple_rules_same_domain(conn):
    db.add_rule(conn, "Block YouTube", {"domains": ["youtube.com"]})
    db.add_rule(conn, "Limit YouTube", {"domains": ["youtube.com"]})
    conflicts = smart.find_conflicts(conn)
    assert len(conflicts) == 1
    assert conflicts[0]["domain"] == "youtube.com"


@pytest.mark.asyncio
async def test_suggest_rules_empty(conn):
    suggestions = await smart.suggest_rules(conn, "key")
    assert suggestions == []


@pytest.mark.asyncio
async def test_suggest_rules_with_data(conn):
    db.save_seen(conn, "tiktok.com", "social")
    for i in range(10):
        db.log_activity(conn, "", "", "", "tiktok.com", "allow")
    suggestions = await smart.suggest_rules(conn, "key")
    assert len(suggestions) > 0
    assert any("tiktok.com" in s for s in suggestions)


def test_coverage_report_empty(conn):
    report = smart.coverage_report(conn)
    assert report["total_distracting_visits"] == 0
    assert report["coverage_percent"] == 0


def test_coverage_report_with_data(conn):
    db.save_seen(conn, "tiktok.com", "social")
    db.log_activity(conn, "", "", "", "tiktok.com", "block")
    db.log_activity(conn, "", "", "", "tiktok.com", "allow")
    db.log_activity(conn, "", "", "", "tiktok.com", "allow")
    report = smart.coverage_report(conn)
    assert report["total_distracting_visits"] == 3
    assert report["blocked_visits"] == 1


@pytest.mark.asyncio
async def test_explain_block(conn):
    with patch("sentinel.smart.classifier.call_gemini", new_callable=AsyncMock,
               return_value="Blocked because of the social media rule."):
        result = await smart.explain_block(conn, "youtube.com", "key")
        assert "social media" in result


@pytest.mark.asyncio
async def test_explain_block_error():
    with patch("sentinel.smart.classifier.call_gemini", new_callable=AsyncMock,
               side_effect=Exception("fail")):
        # Need to pass a conn for db.get_rules
        import sqlite3
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        c.execute("CREATE TABLE rules (id INTEGER PRIMARY KEY, text TEXT, parsed TEXT, active INTEGER DEFAULT 1)")
        result = await smart.explain_block(c, "test.com", "key")
        assert "test.com" in result
        c.close()


def test_coverage_with_unseen(conn):
    db.log_activity(conn, "", "", "", "unknown.com", "allow")
    report = smart.coverage_report(conn)
    # unknown.com has no seen category, so it doesn't count
    assert report["total_distracting_visits"] == 0
