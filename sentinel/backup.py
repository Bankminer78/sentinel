"""Backup and restore Sentinel data."""
import json, shutil, os, time
from pathlib import Path
from . import importer

_DEFAULT_DIR = Path.home() / ".config" / "sentinel" / "backups"


def _default_dir() -> Path:
    _DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
    return _DEFAULT_DIR


def create_backup(conn, backup_path: str = None) -> str:
    data = importer.export_all(conn)
    data["backup_version"] = 1
    data["backup_ts"] = time.time()
    if backup_path is None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup_path = str(_default_dir() / f"sentinel-backup-{stamp}.json")
    p = Path(backup_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2))
    return str(p)


def restore_backup(conn, backup_path: str) -> dict:
    p = Path(backup_path)
    if not p.exists():
        return {"error": "not found", "rules": 0, "goals": 0, "partners": 0, "config": 0}
    try:
        data = json.loads(p.read_text())
    except Exception:
        return {"error": "invalid", "rules": 0, "goals": 0, "partners": 0, "config": 0}
    return importer.import_all(conn, data)


def list_backups(backup_dir: str = None) -> list:
    d = Path(backup_dir) if backup_dir else _default_dir()
    if not d.exists():
        return []
    out = []
    for f in sorted(d.glob("sentinel-backup-*.json"), reverse=True):
        try:
            st = f.stat()
            out.append({"path": str(f), "name": f.name,
                        "size": st.st_size, "mtime": st.st_mtime})
        except OSError:
            continue
    return out


def delete_backup(backup_path: str):
    p = Path(backup_path)
    if p.exists():
        p.unlink()


def auto_backup_daily(conn, max_backups: int = 7) -> str:
    path = create_backup(conn)
    backups = list_backups()
    for old in backups[max_backups:]:
        delete_backup(old["path"])
    return path


def get_backup_size(backup_path: str) -> int:
    p = Path(backup_path)
    return p.stat().st_size if p.exists() else 0


def verify_backup(backup_path: str) -> bool:
    p = Path(backup_path)
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text())
    except Exception:
        return False
    return isinstance(data, dict) and "rules" in data
