"""Tests for sentinel.feature_flags."""
import pytest
from sentinel import feature_flags, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_default_flag_value(conn):
    # ai_coach is True by default
    assert feature_flags.get_flag(conn, "ai_coach") is True


def test_default_flag_false(conn):
    assert feature_flags.get_flag(conn, "telemetry") is False


def test_set_flag(conn):
    feature_flags.set_flag(conn, "experimental_vision", True)
    assert feature_flags.get_flag(conn, "experimental_vision") is True


def test_unset_flag(conn):
    feature_flags.set_flag(conn, "ai_coach", False)
    assert feature_flags.get_flag(conn, "ai_coach") is False


def test_enable_convenience(conn):
    feature_flags.enable(conn, "telemetry")
    assert feature_flags.get_flag(conn, "telemetry") is True


def test_disable_convenience(conn):
    feature_flags.disable(conn, "ai_coach")
    assert feature_flags.get_flag(conn, "ai_coach") is False


def test_is_enabled(conn):
    feature_flags.enable(conn, "advanced_nlp")
    assert feature_flags.is_enabled(conn, "advanced_nlp") is True


def test_get_all_flags(conn):
    flags = feature_flags.get_all_flags(conn)
    assert "ai_coach" in flags
    assert len(flags) >= 10


def test_reset_flag(conn):
    feature_flags.set_flag(conn, "ai_coach", False)
    feature_flags.reset_flag(conn, "ai_coach")
    assert feature_flags.get_flag(conn, "ai_coach") is True  # Back to default


def test_reset_all(conn):
    feature_flags.set_flag(conn, "ai_coach", False)
    feature_flags.set_flag(conn, "telemetry", True)
    feature_flags.reset_all(conn)
    assert feature_flags.get_flag(conn, "ai_coach") is True  # Default


def test_list_flags():
    flags = feature_flags.list_flags()
    assert len(flags) > 10
    assert "ai_coach" in flags


def test_unknown_flag(conn):
    assert feature_flags.get_flag(conn, "nonexistent") is False
