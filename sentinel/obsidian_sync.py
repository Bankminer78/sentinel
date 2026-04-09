"""Obsidian integration — export Sentinel data to Obsidian vault."""
from pathlib import Path
from datetime import datetime
from . import db


def set_vault_path(conn, path: str):
    db.set_config(conn, "obsidian_vault", path)


def get_vault_path(conn) -> str:
    return db.get_config(conn, "obsidian_vault", "") or ""


def is_configured(conn) -> bool:
    path = get_vault_path(conn)
    return bool(path) and Path(path).exists()


def export_rule_to_vault(conn, rule: dict) -> str:
    vault = get_vault_path(conn)
    if not vault:
        return ""
    p = Path(vault) / "Sentinel" / "Rules"
    p.mkdir(parents=True, exist_ok=True)
    filename = f"rule-{rule['id']}-{rule['text'][:30].replace('/', '-')}.md"
    file_path = p / filename
    content = f"# {rule['text']}\n\n- **ID:** {rule['id']}\n- **Active:** {rule['active']}\n"
    file_path.write_text(content)
    return str(file_path)


def export_daily_note(conn, date_str: str = None) -> str:
    vault = get_vault_path(conn)
    if not vault:
        return ""
    d = date_str or datetime.now().strftime("%Y-%m-%d")
    p = Path(vault) / "Sentinel" / "Daily"
    p.mkdir(parents=True, exist_ok=True)
    file_path = p / f"{d}.md"
    try:
        from . import stats as stats_mod
        score = stats_mod.calculate_score(conn, d)
    except Exception:
        score = 0
    content = f"# {d}\n\n## Productivity\n\nScore: {score}/100\n\n## Activity\n\n"
    file_path.write_text(content)
    return str(file_path)


def export_journal_entries(conn) -> int:
    vault = get_vault_path(conn)
    if not vault:
        return 0
    try:
        entries = conn.execute("SELECT * FROM journal ORDER BY id").fetchall()
    except Exception:
        return 0
    p = Path(vault) / "Sentinel" / "Journal"
    p.mkdir(parents=True, exist_ok=True)
    count = 0
    for e in entries:
        d = dict(e)
        filename = f"journal-{d.get('id')}.md"
        (p / filename).write_text(
            f"# Journal Entry {d.get('id')}\n\n{d.get('content') or ''}\n")
        count += 1
    return count


def export_all(conn) -> dict:
    if not is_configured(conn):
        return {"error": "not configured"}
    rules_count = 0
    for r in db.get_rules(conn, active_only=False):
        if export_rule_to_vault(conn, r):
            rules_count += 1
    journal_count = export_journal_entries(conn)
    daily_file = export_daily_note(conn)
    return {
        "rules": rules_count,
        "journal": journal_count,
        "daily_note": daily_file,
    }


def get_vault_info(conn) -> dict:
    path = get_vault_path(conn)
    if not path:
        return {"configured": False}
    p = Path(path)
    return {
        "configured": True,
        "path": path,
        "exists": p.exists(),
        "is_dir": p.is_dir() if p.exists() else False,
    }
