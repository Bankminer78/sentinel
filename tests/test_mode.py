"""Tests for sentinel.mode."""
from sentinel import mode


def test_list_modes():
    modes = mode.list_modes()
    names = {m["name"] for m in modes}
    assert "work" in names
    assert "sleep" in names
    assert "relax" in names


def test_switch_mode(conn):
    r = mode.switch_mode(conn, "work")
    assert r["ok"] is True
    assert r["mode"] == "work"


def test_switch_mode_unknown(conn):
    r = mode.switch_mode(conn, "nonexistent")
    assert r["ok"] is False


def test_get_current_mode_default(conn):
    assert mode.get_current_mode(conn) == "relax"


def test_get_current_mode_after_switch(conn):
    mode.switch_mode(conn, "study")
    assert mode.get_current_mode(conn) == "study"


def test_is_blocked_in_mode_work(conn):
    mode.switch_mode(conn, "work")
    assert mode.is_blocked_in_mode(conn, "social") is True
    assert mode.is_blocked_in_mode(conn, "news") is False


def test_is_blocked_in_mode_relax(conn):
    mode.switch_mode(conn, "relax")
    assert mode.is_blocked_in_mode(conn, "social") is False


def test_sleep_blocks_adult(conn):
    mode.switch_mode(conn, "sleep")
    assert mode.is_blocked_in_mode(conn, "adult") is True


def test_family_mode(conn):
    mode.switch_mode(conn, "family")
    assert mode.is_blocked_in_mode(conn, "adult") is True
    assert mode.is_blocked_in_mode(conn, "gaming") is True
    assert mode.is_blocked_in_mode(conn, "social") is False


def test_switch_returns_rules_and_categories(conn):
    r = mode.switch_mode(conn, "work")
    assert isinstance(r["rules"], list)
    assert "social" in r["block_categories"]


def test_all_modes_have_keys():
    for m in mode.list_modes():
        assert "name" in m
        assert "rules" in m
        assert "block_categories" in m
