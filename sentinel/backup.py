"""Backup and restore Sentinel data — full SQLite snapshot."""
import shutil, time
from pathlib import Path

_DEFAULT_DIR = Path.home() / ".config" / "sentinel" / "backups"


def _default_dir() -> Path:
    _DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
    return _DEFAULT_DIR


def create_backup(conn, backup_path: str = None) -> str:
    """Create a full SQLite backup. Uses sqlite3.backup() for consistency."""
    if backup_path is None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup_path = str(_default_dir() / f"sentinel-{stamp}.db")
    p = Path(backup_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    import sqlite3
    dst = sqlite3.connect(str(p))
    try:
        conn.backup(dst)
    finally:
        dst.close()
    return str(p)


def restore_backup(conn, backup_path: str) -> dict:
    """Restore: copy backup over current DB. Returns row counts."""
    p = Path(backup_path)
    if not p.exists():
        return {"error": "not found"}
    import sqlite3
    src = sqlite3.connect(str(p))
    try:
        src.backup(conn)
    finally:
        src.close()
    counts = {}
    for table in ("rules", "activity_log", "seen_domains", "ai_kv", "ai_docs"):
        try:
            r = conn.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()
            counts[table] = r[0] if r else 0
        except Exception:
            counts[table] = 0
    return counts


def list_backups(backup_dir: str = None) -> list:
    d = Path(backup_dir) if backup_dir else _default_dir()
    if not d.exists():
        return []
    out = []
    for f in sorted(d.glob("sentinel-*.db"), reverse=True):
        try:
            st = f.stat()
            out.append({"path": str(f), "name": f.name, "size": st.st_size, "mtime": st.st_mtime})
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
    # Check SQLite magic header
    try:
        with open(p, "rb") as f:
            header = f.read(16)
        if not header.startswith(b"SQLite format 3"):
            return False
        import sqlite3
        c = sqlite3.connect(str(p))
        c.execute("PRAGMA integrity_check").fetchone()
        c.close()
        return True
    except Exception:
        return False
