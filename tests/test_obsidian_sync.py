"""Tests for sentinel.obsidian_sync."""
import pytest
from pathlib import Path
from sentinel import obsidian_sync as os, db


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_set_get_vault(conn):
    os.set_vault_path(conn, "/tmp/test_vault")
    assert os.get_vault_path(conn) == "/tmp/test_vault"


def test_is_configured_false(conn):
    assert os.is_configured(conn) is False


def test_is_configured_nonexistent(conn):
    os.set_vault_path(conn, "/nonexistent/path")
    assert os.is_configured(conn) is False


def test_is_configured_true(conn, tmp_path):
    os.set_vault_path(conn, str(tmp_path))
    assert os.is_configured(conn) is True


def test_export_rule(conn, tmp_path):
    os.set_vault_path(conn, str(tmp_path))
    rule = {"id": 1, "text": "Block YouTube", "active": 1}
    path = os.export_rule_to_vault(conn, rule)
    assert path
    assert Path(path).exists()


def test_export_rule_no_vault(conn):
    rule = {"id": 1, "text": "Test", "active": 1}
    assert os.export_rule_to_vault(conn, rule) == ""


def test_export_daily_note(conn, tmp_path):
    os.set_vault_path(conn, str(tmp_path))
    path = os.export_daily_note(conn, "2026-04-09")
    assert Path(path).exists()


def test_export_journal_entries_no_vault(conn):
    assert os.export_journal_entries(conn) == 0


def test_export_all_not_configured(conn):
    result = os.export_all(conn)
    assert "error" in result


def test_export_all(conn, tmp_path):
    os.set_vault_path(conn, str(tmp_path))
    db.add_rule(conn, "Test rule")
    result = os.export_all(conn)
    assert result.get("rules", 0) >= 1


def test_vault_info_not_configured(conn):
    info = os.get_vault_info(conn)
    assert info["configured"] is False


def test_vault_info_configured(conn, tmp_path):
    os.set_vault_path(conn, str(tmp_path))
    info = os.get_vault_info(conn)
    assert info["configured"] is True
    assert info["exists"] is True
