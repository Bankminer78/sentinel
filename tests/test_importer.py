"""Tests for sentinel.importer — export/import rules, goals, partners, config."""

import json

import pytest

from sentinel import db, importer, partners, stats


class TestExportRules:
    def test_export_empty(self, conn):
        data = json.loads(importer.export_rules(conn))
        assert data["rules"] == []
        assert data["version"] == 1

    def test_export_includes_text(self, conn):
        db.add_rule(conn, "Block YouTube", {"domains": ["youtube.com"]})
        data = json.loads(importer.export_rules(conn))
        assert data["rules"][0]["text"] == "Block YouTube"

    def test_export_includes_active_flag(self, conn):
        db.add_rule(conn, "r1")
        data = json.loads(importer.export_rules(conn))
        assert data["rules"][0]["active"] is True


class TestImportRules:
    def test_import_empty_list(self, conn):
        n = importer.import_rules(conn, json.dumps({"rules": []}))
        assert n == 0

    def test_import_single(self, conn):
        payload = json.dumps({"rules": [{"text": "Block X"}]})
        n = importer.import_rules(conn, payload)
        assert n == 1
        assert db.get_rules(conn)[0]["text"] == "Block X"

    def test_import_multiple(self, conn):
        payload = json.dumps({"rules": [{"text": "A"}, {"text": "B"}, {"text": "C"}]})
        assert importer.import_rules(conn, payload) == 3

    def test_import_skips_missing_text(self, conn):
        payload = json.dumps({"rules": [{"text": "A"}, {"parsed": {}}]})
        assert importer.import_rules(conn, payload) == 1

    def test_import_bad_json(self, conn):
        assert importer.import_rules(conn, "{{not json}}") == 0

    def test_export_import_roundtrip(self, conn):
        db.add_rule(conn, "rule A")
        db.add_rule(conn, "rule B")
        payload = importer.export_rules(conn)
        # import into a fresh conn
        from pathlib import Path
        c2 = db.connect(Path(":memory:"))
        n = importer.import_rules(c2, payload)
        assert n == 2
        texts = [r["text"] for r in db.get_rules(c2)]
        assert "rule A" in texts and "rule B" in texts
        c2.close()


class TestExportAll:
    def test_export_all_has_keys(self, conn):
        out = importer.export_all(conn)
        assert set(["version", "rules", "goals", "partners", "config"]).issubset(out.keys())

    def test_export_all_excludes_api_key(self, conn):
        db.set_config(conn, "gemini_api_key", "SECRET")
        db.set_config(conn, "theme", "dark")
        out = importer.export_all(conn)
        assert "gemini_api_key" not in out["config"]
        assert out["config"].get("theme") == "dark"

    def test_export_all_includes_partners(self, conn):
        partners.add_partner(conn, "Alice", "u1")
        out = importer.export_all(conn)
        assert out["partners"][0]["name"] == "Alice"

    def test_export_all_includes_goals(self, conn):
        stats.add_goal(conn, "focus", "max_seconds", 3600)
        out = importer.export_all(conn)
        assert out["goals"][0]["name"] == "focus"


class TestImportAll:
    def test_import_all_full(self, conn):
        data = {
            "rules": [{"text": "Block YouTube"}],
            "goals": [{"name": "focus", "target_type": "max_seconds", "target_value": 3600}],
            "partners": [{"name": "Alice", "contact": "u1", "method": "webhook"}],
            "config": {"theme": "dark"},
        }
        counts = importer.import_all(conn, data)
        assert counts == {"rules": 1, "goals": 1, "partners": 1, "config": 1}

    def test_import_all_skips_api_key(self, conn):
        counts = importer.import_all(conn, {"config": {"gemini_api_key": "X"}})
        assert counts["config"] == 0
        assert db.get_config(conn, "gemini_api_key") is None

    def test_import_all_accepts_json_string(self, conn):
        data = json.dumps({"rules": [{"text": "r"}]})
        counts = importer.import_all(conn, data)
        assert counts["rules"] == 1

    def test_import_all_bad_data(self, conn):
        assert importer.import_all(conn, "not-json") == {"rules": 0, "goals": 0, "partners": 0, "config": 0}
        assert importer.import_all(conn, 42) == {"rules": 0, "goals": 0, "partners": 0, "config": 0}
