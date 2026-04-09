"""Tests for sentinel.backup."""
import pytest
import json
import tempfile
from pathlib import Path
from sentinel import backup, db


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


@pytest.fixture
def tmp_backup_path(tmp_path):
    return str(tmp_path / "backup.json")


def test_create_backup(conn, tmp_backup_path):
    db.add_rule(conn, "Test rule")
    path = backup.create_backup(conn, tmp_backup_path)
    assert Path(path).exists()


def test_backup_contents(conn, tmp_backup_path):
    db.add_rule(conn, "Rule 1")
    path = backup.create_backup(conn, tmp_backup_path)
    data = json.loads(Path(path).read_text())
    assert data["backup_version"] == 1
    assert "backup_ts" in data


def test_restore_backup(conn, tmp_backup_path):
    db.add_rule(conn, "Original")
    backup.create_backup(conn, tmp_backup_path)
    db.delete_rule(conn, 1)
    assert db.get_rules(conn) == []
    backup.restore_backup(conn, tmp_backup_path)
    assert len(db.get_rules(conn)) == 1


def test_restore_nonexistent(conn):
    result = backup.restore_backup(conn, "/nonexistent/path.json")
    assert "error" in result


def test_restore_invalid_json(conn, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not valid json")
    result = backup.restore_backup(conn, str(bad))
    assert "error" in result


def test_list_backups(tmp_path):
    # Use temp dir
    d = tmp_path / "backups"
    d.mkdir()
    (d / "sentinel-backup-20260409.json").write_text("{}")
    (d / "sentinel-backup-20260408.json").write_text("{}")
    (d / "other-file.json").write_text("{}")
    backups = backup.list_backups(str(d))
    assert len(backups) == 2


def test_list_backups_empty(tmp_path):
    assert backup.list_backups(str(tmp_path)) == []


def test_delete_backup(tmp_backup_path):
    Path(tmp_backup_path).write_text("{}")
    backup.delete_backup(tmp_backup_path)
    assert not Path(tmp_backup_path).exists()


def test_delete_nonexistent(tmp_path):
    backup.delete_backup(str(tmp_path / "ghost.json"))  # Should not raise


def test_get_backup_size(tmp_backup_path):
    Path(tmp_backup_path).write_text('{"data": "test"}')
    size = backup.get_backup_size(tmp_backup_path)
    assert size > 0


def test_get_backup_size_missing(tmp_path):
    assert backup.get_backup_size(str(tmp_path / "missing.json")) == 0


def test_verify_backup_valid(conn, tmp_backup_path):
    backup.create_backup(conn, tmp_backup_path)
    assert backup.verify_backup(tmp_backup_path) is True


def test_verify_backup_missing():
    assert backup.verify_backup("/nonexistent.json") is False


def test_verify_backup_invalid(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    assert backup.verify_backup(str(bad)) is False
