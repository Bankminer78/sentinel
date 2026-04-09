"""Tests for sentinel.backup — SQLite backup format."""
import pytest
from pathlib import Path
from sentinel import backup, db


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


@pytest.fixture
def tmp_backup_path(tmp_path):
    return str(tmp_path / "backup.db")


def test_create_backup(conn, tmp_backup_path):
    db.add_rule(conn, "Test rule")
    path = backup.create_backup(conn, tmp_backup_path)
    assert Path(path).exists()


def test_backup_is_sqlite(conn, tmp_backup_path):
    db.add_rule(conn, "Rule 1")
    backup.create_backup(conn, tmp_backup_path)
    # Should be a valid SQLite file
    import sqlite3
    c = sqlite3.connect(tmp_backup_path)
    rows = c.execute("SELECT text FROM rules").fetchall()
    assert len(rows) == 1
    c.close()


def test_restore_backup(conn, tmp_backup_path):
    db.add_rule(conn, "Original")
    backup.create_backup(conn, tmp_backup_path)
    db.delete_rule(conn, 1)
    assert db.get_rules(conn) == []
    backup.restore_backup(conn, tmp_backup_path)
    assert len(db.get_rules(conn)) == 1


def test_restore_nonexistent(conn):
    result = backup.restore_backup(conn, "/nonexistent/path.db")
    assert "error" in result


def test_list_backups(tmp_path):
    d = tmp_path / "backups"
    d.mkdir()
    (d / "sentinel-20260409.db").write_text("placeholder")
    (d / "sentinel-20260408.db").write_text("placeholder")
    (d / "other-file.db").write_text("placeholder")
    backups = backup.list_backups(str(d))
    assert len(backups) == 2


def test_list_backups_empty(tmp_path):
    assert backup.list_backups(str(tmp_path)) == []


def test_delete_backup(tmp_backup_path):
    Path(tmp_backup_path).write_text("placeholder")
    backup.delete_backup(tmp_backup_path)
    assert not Path(tmp_backup_path).exists()


def test_delete_nonexistent(tmp_path):
    backup.delete_backup(str(tmp_path / "ghost.db"))  # Should not raise


def test_get_backup_size(tmp_backup_path):
    Path(tmp_backup_path).write_text('placeholder')
    size = backup.get_backup_size(tmp_backup_path)
    assert size > 0


def test_get_backup_size_missing(tmp_path):
    assert backup.get_backup_size(str(tmp_path / "missing.db")) == 0


def test_verify_backup_valid(conn, tmp_backup_path):
    backup.create_backup(conn, tmp_backup_path)
    assert backup.verify_backup(tmp_backup_path) is True


def test_verify_backup_missing():
    assert backup.verify_backup("/nonexistent.db") is False


def test_verify_backup_invalid(tmp_path):
    bad = tmp_path / "bad.db"
    bad.write_text("not a sqlite file")
    assert backup.verify_backup(str(bad)) is False


def test_auto_backup_daily(conn, tmp_path, monkeypatch):
    # Redirect default dir to tmp
    monkeypatch.setattr(backup, "_DEFAULT_DIR", tmp_path)
    db.add_rule(conn, "Test")
    path = backup.auto_backup_daily(conn, max_backups=2)
    assert Path(path).exists()
