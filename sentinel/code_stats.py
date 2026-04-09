"""Code stats — track coding activity from git commits."""
import subprocess, time
from datetime import datetime, timedelta


def get_commits_today(repo_path: str = None) -> list:
    """Get today's commits from a git repo."""
    cmd = ["git", "log", "--since=midnight", "--pretty=format:%h|%s|%ad|%an",
           "--date=short"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10,
                           cwd=repo_path or ".")
        if r.returncode != 0:
            return []
        commits = []
        for line in r.stdout.strip().splitlines():
            if not line:
                continue
            parts = line.split("|", 3)
            if len(parts) >= 4:
                commits.append({
                    "hash": parts[0], "message": parts[1],
                    "date": parts[2], "author": parts[3],
                })
        return commits
    except Exception:
        return []


def count_commits(repo_path: str = None, since: str = "1.week.ago") -> int:
    try:
        r = subprocess.run(
            ["git", "rev-list", "--count", f"--since={since}", "HEAD"],
            capture_output=True, text=True, timeout=10, cwd=repo_path or ".")
        if r.returncode == 0:
            return int(r.stdout.strip() or 0)
    except Exception:
        pass
    return 0


def lines_changed(repo_path: str = None, since: str = "1.week.ago") -> dict:
    try:
        r = subprocess.run(
            ["git", "log", f"--since={since}", "--numstat", "--pretty="],
            capture_output=True, text=True, timeout=15, cwd=repo_path or ".")
        if r.returncode != 0:
            return {"added": 0, "deleted": 0}
        added, deleted = 0, 0
        for line in r.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                try:
                    added += int(parts[0])
                    deleted += int(parts[1])
                except Exception:
                    pass
        return {"added": added, "deleted": deleted}
    except Exception:
        return {"added": 0, "deleted": 0}


def top_files(repo_path: str = None, since: str = "1.month.ago") -> list:
    try:
        r = subprocess.run(
            ["git", "log", f"--since={since}", "--name-only", "--pretty=format:"],
            capture_output=True, text=True, timeout=15, cwd=repo_path or ".")
        if r.returncode != 0:
            return []
        from collections import Counter
        files = Counter()
        for line in r.stdout.splitlines():
            if line.strip():
                files[line.strip()] += 1
        return [{"file": f, "changes": c} for f, c in files.most_common(10)]
    except Exception:
        return []


def commit_streak(repo_path: str = None) -> int:
    """Consecutive days with at least one commit."""
    try:
        r = subprocess.run(
            ["git", "log", "--pretty=format:%ad", "--date=short"],
            capture_output=True, text=True, timeout=10, cwd=repo_path or ".")
        if r.returncode != 0:
            return 0
        dates = set(r.stdout.strip().splitlines())
        current = datetime.now().date()
        days = 0
        while current.strftime("%Y-%m-%d") in dates:
            days += 1
            current -= timedelta(days=1)
        return days
    except Exception:
        return 0


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS code_stats (
        id INTEGER PRIMARY KEY, repo TEXT, commits INTEGER,
        lines_added INTEGER, lines_deleted INTEGER, date TEXT, ts REAL
    )""")


def log_daily_stats(conn, repo_path: str = ".") -> int:
    _ensure_table(conn)
    commits = count_commits(repo_path, "1.day.ago")
    lines = lines_changed(repo_path, "1.day.ago")
    date_str = datetime.now().strftime("%Y-%m-%d")
    cur = conn.execute(
        "INSERT INTO code_stats (repo, commits, lines_added, lines_deleted, date, ts) VALUES (?, ?, ?, ?, ?, ?)",
        (repo_path, commits, lines["added"], lines["deleted"], date_str, time.time()))
    conn.commit()
    return cur.lastrowid


def get_stats_log(conn, days: int = 30) -> list:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT * FROM code_stats WHERE ts > ? ORDER BY ts DESC", (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def weekly_summary(conn) -> dict:
    _ensure_table(conn)
    cutoff = time.time() - 7 * 86400
    rows = conn.execute(
        "SELECT * FROM code_stats WHERE ts > ?", (cutoff,)).fetchall()
    total_commits = sum(r["commits"] or 0 for r in rows)
    total_added = sum(r["lines_added"] or 0 for r in rows)
    total_deleted = sum(r["lines_deleted"] or 0 for r in rows)
    return {
        "commits": total_commits,
        "lines_added": total_added,
        "lines_deleted": total_deleted,
        "net_lines": total_added - total_deleted,
    }
