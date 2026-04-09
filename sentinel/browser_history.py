"""Import browser history to bootstrap skiplist/seen_domains."""
import sqlite3, shutil, tempfile, time, re
from pathlib import Path
from collections import Counter
from . import db

CHROME_HISTORY = Path.home() / "Library/Application Support/Google/Chrome/Default/History"
ARC_HISTORY = Path.home() / "Library/Application Support/Arc/User Data/Default/History"
SAFARI_HISTORY = Path.home() / "Library/Safari/History.db"


def _extract_domain(url: str) -> str:
    m = re.match(r'^(?:https?://)?(?:www\.)?([^/\?#]+)', url.lower())
    return m.group(1) if m else ""


def _read_chromium(path: Path, since_days: int = 7) -> list:
    if not path.exists():
        return []
    # Copy to temp file since Chrome may have it locked
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        shutil.copy(str(path), tmp.name)
        tmp_path = tmp.name
    try:
        conn = sqlite3.connect(tmp_path)
        conn.row_factory = sqlite3.Row
        # Chrome stores time as microseconds since 1601
        since_us = int(((time.time() - since_days * 86400) + 11644473600) * 1_000_000)
        rows = conn.execute(
            "SELECT url, title, visit_count FROM urls WHERE last_visit_time > ? ORDER BY visit_count DESC",
            (since_us,)).fetchall()
        result = [dict(r) for r in rows]
        conn.close()
        return result
    except Exception:
        return []
    finally:
        try:
            Path(tmp_path).unlink()
        except Exception:
            pass


def read_chrome_history(since_days: int = 7) -> list:
    return _read_chromium(CHROME_HISTORY, since_days)


def read_arc_history(since_days: int = 7) -> list:
    return _read_chromium(ARC_HISTORY, since_days)


def read_safari_history(since_days: int = 7) -> list:
    """Safari stores history differently."""
    if not SAFARI_HISTORY.exists():
        return []
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        shutil.copy(str(SAFARI_HISTORY), tmp.name)
        tmp_path = tmp.name
    try:
        conn = sqlite3.connect(tmp_path)
        conn.row_factory = sqlite3.Row
        since_apple = time.time() - since_days * 86400 - 978307200
        rows = conn.execute(
            "SELECT url FROM history_visits JOIN history_items ON history_visits.history_item = history_items.id WHERE visit_time > ?",
            (since_apple,)).fetchall()
        result = [{"url": r["url"], "visit_count": 1} for r in rows]
        conn.close()
        return result
    except Exception:
        return []
    finally:
        try:
            Path(tmp_path).unlink()
        except Exception:
            pass


def top_domains(history: list, limit: int = 50) -> list:
    """Count visits per domain."""
    c = Counter()
    for h in history:
        d = _extract_domain(h.get("url", ""))
        if d:
            c[d] += h.get("visit_count", 1)
    return [{"domain": d, "visits": v} for d, v in c.most_common(limit)]


def bootstrap_skiplist_from_history(conn, source: str = "chrome") -> int:
    """Read history, save top domains to seen_domains as 'none'."""
    history_fn = {"chrome": read_chrome_history, "arc": read_arc_history,
                  "safari": read_safari_history}.get(source)
    if not history_fn:
        return 0
    history = history_fn()
    top = top_domains(history, limit=100)
    count = 0
    for item in top:
        d = item["domain"]
        if not db.get_seen(conn, d):
            db.save_seen(conn, d, "none")
            count += 1
    return count
