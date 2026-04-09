"""Tests for sentinel.sensitivity — strict/normal/lax modes."""

import pytest

from sentinel import sensitivity


class TestLevels:
    def test_has_three_levels(self):
        assert set(sensitivity.LEVELS) == {"strict", "normal", "lax"}

    def test_each_level_has_fields(self):
        for cfg in sensitivity.LEVELS.values():
            assert "auto_block_threshold" in cfg
            assert "allow_negotiation" in cfg
            assert "penalty_multiplier" in cfg

    def test_list_levels(self):
        assert sorted(sensitivity.list_levels()) == ["lax", "normal", "strict"]


class TestSetGet:
    def test_default_is_normal(self, conn):
        assert sensitivity.get_sensitivity(conn) == "normal"

    def test_set_and_get(self, conn):
        sensitivity.set_sensitivity(conn, "strict")
        assert sensitivity.get_sensitivity(conn) == "strict"

    def test_set_lax(self, conn):
        sensitivity.set_sensitivity(conn, "lax")
        assert sensitivity.get_sensitivity(conn) == "lax"

    def test_invalid_raises(self, conn):
        with pytest.raises(ValueError):
            sensitivity.set_sensitivity(conn, "bogus")

    def test_corrupted_config_falls_back(self, conn):
        from sentinel import db
        db.set_config(conn, "sensitivity_level", "garbage")
        assert sensitivity.get_sensitivity(conn) == "normal"


class TestConfig:
    def test_config_strict(self, conn):
        sensitivity.set_sensitivity(conn, "strict")
        cfg = sensitivity.get_sensitivity_config(conn)
        assert cfg["allow_negotiation"] is False
        assert cfg["penalty_multiplier"] == 2.0

    def test_config_lax(self, conn):
        sensitivity.set_sensitivity(conn, "lax")
        cfg = sensitivity.get_sensitivity_config(conn)
        assert cfg["penalty_multiplier"] == 0.5

    def test_apply_penalty_strict_doubles(self, conn):
        sensitivity.set_sensitivity(conn, "strict")
        assert sensitivity.apply_penalty(conn, 5.0) == 10.0

    def test_apply_penalty_lax_halves(self, conn):
        sensitivity.set_sensitivity(conn, "lax")
        assert sensitivity.apply_penalty(conn, 10.0) == 5.0

    def test_is_negotiation_allowed(self, conn):
        sensitivity.set_sensitivity(conn, "strict")
        assert sensitivity.is_negotiation_allowed(conn) is False
        sensitivity.set_sensitivity(conn, "normal")
        assert sensitivity.is_negotiation_allowed(conn) is True

    def test_auto_block_threshold(self, conn):
        sensitivity.set_sensitivity(conn, "strict")
        assert sensitivity.auto_block_threshold(conn) == 0.5
        sensitivity.set_sensitivity(conn, "lax")
        assert sensitivity.auto_block_threshold(conn) == 0.9
