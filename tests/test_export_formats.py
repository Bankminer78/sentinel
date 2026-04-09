"""Tests for sentinel.export_formats — CSV, Markdown, HTML exports."""

import csv
import io

import pytest

from sentinel import db, export_formats


class TestRulesToCsv:
    def test_empty(self, conn):
        out = export_formats.rules_to_csv(conn)
        assert "id,text,action,active" in out.splitlines()[0]

    def test_with_rules(self, conn):
        db.add_rule(conn, "Block YouTube")
        out = export_formats.rules_to_csv(conn)
        reader = list(csv.DictReader(io.StringIO(out)))
        assert len(reader) == 1
        assert reader[0]["text"] == "Block YouTube"

    def test_includes_active_flag(self, conn):
        db.add_rule(conn, "rule A")
        out = export_formats.rules_to_csv(conn)
        reader = list(csv.DictReader(io.StringIO(out)))
        assert reader[0]["active"] == "True"


class TestRulesToMarkdown:
    def test_empty(self, conn):
        out = export_formats.rules_to_markdown(conn)
        assert "# Sentinel Rules" in out
        assert "No rules" in out

    def test_with_rules(self, conn):
        db.add_rule(conn, "Block X")
        out = export_formats.rules_to_markdown(conn)
        assert "| ID |" in out
        assert "Block X" in out

    def test_escapes_pipes(self, conn):
        db.add_rule(conn, "rule|with|pipes")
        out = export_formats.rules_to_markdown(conn)
        assert "rule\\|with\\|pipes" in out


class TestStatsToCsv:
    def test_has_header(self, conn):
        out = export_formats.stats_to_csv(conn, days=3)
        assert "date" in out.splitlines()[0]
        assert "score" in out.splitlines()[0]

    def test_days_count(self, conn):
        out = export_formats.stats_to_csv(conn, days=5)
        reader = list(csv.DictReader(io.StringIO(out)))
        assert len(reader) == 5


class TestActivityToCsv:
    def test_empty(self, conn):
        out = export_formats.activity_to_csv(conn)
        assert "ts,app,title" in out.splitlines()[0]

    def test_with_activity(self, conn):
        db.log_activity(conn, "Safari", "T", "https://x.com/p", "x.com", verdict="allow")
        out = export_formats.activity_to_csv(conn, days=1)
        reader = list(csv.DictReader(io.StringIO(out)))
        assert len(reader) == 1
        assert reader[0]["domain"] == "x.com"
        assert reader[0]["verdict"] == "allow"


class TestFullReportMarkdown:
    def test_has_header(self, conn):
        out = export_formats.full_report_markdown(conn)
        assert "# Sentinel Report" in out

    def test_has_sections(self, conn):
        out = export_formats.full_report_markdown(conn)
        assert "## Today" in out
        assert "## Last 7 Days" in out
        assert "## Top Distractions" in out
        assert "## Rules" in out

    def test_empty_top_distractions(self, conn):
        out = export_formats.full_report_markdown(conn)
        assert "_None._" in out


class TestFullReportHtml:
    def test_is_html(self, conn):
        out = export_formats.full_report_html(conn)
        assert out.startswith("<!doctype html>")
        assert "</html>" in out

    def test_has_h1(self, conn):
        out = export_formats.full_report_html(conn)
        assert "<h1>Sentinel Report</h1>" in out

    def test_has_h2(self, conn):
        out = export_formats.full_report_html(conn)
        assert "<h2>Today</h2>" in out
