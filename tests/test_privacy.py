"""Tests for sentinel.privacy."""
import pytest
import time
from sentinel import privacy, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_default_privacy_level(conn):
    assert privacy.get_privacy_level(conn) == "balanced"


def test_set_minimal(conn):
    privacy.set_privacy_level(conn, "minimal")
    assert privacy.get_privacy_level(conn) == "minimal"


def test_set_full(conn):
    privacy.set_privacy_level(conn, "full")
    assert privacy.get_privacy_level(conn) == "full"


def test_set_invalid(conn):
    with pytest.raises(ValueError):
        privacy.set_privacy_level(conn, "invalid")


def test_get_privacy_config(conn):
    privacy.set_privacy_level(conn, "minimal")
    cfg = privacy.get_privacy_config(conn)
    assert cfg["store_urls"] is False
    assert cfg["llm_enabled"] is False


def test_is_llm_allowed_minimal(conn):
    privacy.set_privacy_level(conn, "minimal")
    assert privacy.is_llm_allowed(conn) is False


def test_is_llm_allowed_balanced(conn):
    privacy.set_privacy_level(conn, "balanced")
    assert privacy.is_llm_allowed(conn) is True


def test_should_store_urls(conn):
    privacy.set_privacy_level(conn, "minimal")
    assert privacy.should_store_urls(conn) is False
    privacy.set_privacy_level(conn, "balanced")
    assert privacy.should_store_urls(conn) is True


def test_should_store_titles(conn):
    privacy.set_privacy_level(conn, "balanced")
    assert privacy.should_store_titles(conn) is False
    privacy.set_privacy_level(conn, "full")
    assert privacy.should_store_titles(conn) is True


def test_redact_email():
    result = privacy.redact_pii("Contact me at john@example.com please")
    assert "[EMAIL]" in result
    assert "john@example.com" not in result


def test_redact_phone():
    result = privacy.redact_pii("Call 555-123-4567")
    assert "[PHONE]" in result


def test_redact_credit_card():
    result = privacy.redact_pii("Card: 4111 1111 1111 1111")
    assert "[CARD]" in result


def test_redact_empty():
    assert privacy.redact_pii("") == ""
    assert privacy.redact_pii(None) is None


def test_wipe_all_requires_confirm(conn):
    assert privacy.wipe_all_data(conn, "wrong") is False


def test_wipe_all_with_confirm(conn):
    db.add_rule(conn, "Test rule")
    assert privacy.wipe_all_data(conn, "DELETE ALL MY DATA") is True
    assert db.get_rules(conn) == []


def test_wipe_old_data(conn):
    # Insert old activity
    conn.execute("INSERT INTO activity_log (ts, app, title) VALUES (?, 'old', 't')",
                 (time.time() - 60 * 86400,))  # 60 days ago
    conn.execute("INSERT INTO activity_log (ts, app, title) VALUES (?, 'new', 't')",
                 (time.time(),))
    conn.commit()
    count = privacy.wipe_old_data(conn, days=30)
    assert count == 1
