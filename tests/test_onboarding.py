"""Tests for sentinel.onboarding — persona-based setup wizard."""

import pytest

from sentinel import db, onboarding, stats as stats_mod, habits as habits_mod


class TestFirstRun:
    def test_first_run_true_on_fresh_db(self, conn):
        assert onboarding.is_first_run(conn) is True

    def test_mark_onboarded(self, conn):
        onboarding.mark_onboarded(conn)
        assert onboarding.is_first_run(conn) is False


class TestPersonas:
    def test_list_personas(self):
        ps = onboarding.list_personas()
        assert "student" in ps
        assert "developer" in ps
        assert "knowledge_worker" in ps
        assert "parent" in ps

    def test_rules_for_each_persona(self):
        for p in onboarding.list_personas():
            rules = onboarding.suggest_initial_rules(p)
            assert len(rules) >= 1
            assert all(isinstance(r, str) for r in rules)

    def test_goals_for_each_persona(self):
        for p in onboarding.list_personas():
            goals = onboarding.suggest_initial_goals(p)
            assert len(goals) >= 1
            for g in goals:
                assert "name" in g and "target_type" in g and "target_value" in g

    def test_habits_for_each_persona(self):
        for p in onboarding.list_personas():
            assert len(onboarding.suggest_initial_habits(p)) >= 1

    def test_unknown_persona_rules(self):
        with pytest.raises(ValueError):
            onboarding.suggest_initial_rules("ceo")

    def test_unknown_persona_goals(self):
        with pytest.raises(ValueError):
            onboarding.suggest_initial_goals("alien")

    def test_unknown_persona_habits(self):
        with pytest.raises(ValueError):
            onboarding.suggest_initial_habits("ghost")


class TestPersonaSetup:
    def test_setup_creates_rules(self, conn):
        out = onboarding.create_persona_setup(conn, "student")
        assert len(out["rule_ids"]) >= 1
        assert len(db.get_rules(conn)) == len(out["rule_ids"])

    def test_setup_creates_goals(self, conn):
        out = onboarding.create_persona_setup(conn, "developer")
        assert len(out["goal_ids"]) >= 1
        assert len(stats_mod.get_goals(conn)) == len(out["goal_ids"])

    def test_setup_creates_habits(self, conn):
        out = onboarding.create_persona_setup(conn, "knowledge_worker")
        assert len(out["habit_ids"]) >= 1
        assert len(habits_mod.get_habits(conn)) == len(out["habit_ids"])

    def test_setup_marks_onboarded(self, conn):
        onboarding.create_persona_setup(conn, "parent")
        assert onboarding.is_first_run(conn) is False

    def test_setup_unknown_raises(self, conn):
        with pytest.raises(ValueError):
            onboarding.create_persona_setup(conn, "cowboy")

    def test_setup_returns_persona(self, conn):
        out = onboarding.create_persona_setup(conn, "parent")
        assert out["persona"] == "parent"
