"""Tests for sentinel.templates — predefined rule templates."""

import pytest

from sentinel import db, templates


class TestListTemplates:
    def test_not_empty(self):
        assert len(templates.list_templates()) > 0

    def test_has_expected_keys(self):
        keys = {t["key"] for t in templates.list_templates()}
        for k in ["work_focus", "deep_work", "no_porn", "no_shopping",
                  "study_mode", "sleep_hygiene", "detox"]:
            assert k in keys

    def test_each_has_fields(self):
        for t in templates.list_templates():
            assert "key" in t and "name" in t and "description" in t
            assert t["rule_count"] >= 1


class TestGetTemplate:
    def test_get_existing(self):
        tpl = templates.get_template("work_focus")
        assert tpl is not None
        assert "rules" in tpl

    def test_get_missing(self):
        assert templates.get_template("nonexistent") is None


class TestApplyTemplate:
    def test_apply_creates_rules(self, conn):
        ids = templates.apply_template(conn, "work_focus")
        assert len(ids) >= 1
        rules = db.get_rules(conn)
        assert len(rules) == len(ids)

    def test_apply_returns_ids(self, conn):
        ids = templates.apply_template(conn, "no_porn")
        assert all(isinstance(i, int) for i in ids)

    def test_apply_unknown_raises(self, conn):
        with pytest.raises(ValueError):
            templates.apply_template(conn, "bogus")

    def test_apply_detox(self, conn):
        ids = templates.apply_template(conn, "detox")
        assert len(ids) == 1
        rules = db.get_rules(conn)
        assert "detox" in rules[0]["text"].lower() or "block" in rules[0]["text"].lower()

    def test_apply_twice_appends(self, conn):
        templates.apply_template(conn, "work_focus")
        n1 = len(db.get_rules(conn))
        templates.apply_template(conn, "work_focus")
        n2 = len(db.get_rules(conn))
        assert n2 == 2 * n1
