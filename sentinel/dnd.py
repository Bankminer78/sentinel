"""Do Not Disturb / Focus mode integration."""
import subprocess, time


def enable_dnd() -> bool:
    """Try to enable macOS Focus/DND."""
    script = 'tell application "System Events" to key code 103 using {control down, option down, command down}'
    try:
        subprocess.run(["osascript", "-e", script], timeout=5, check=False)
        return True
    except Exception:
        return False


def disable_dnd() -> bool:
    """Disable macOS Focus/DND."""
    return enable_dnd()  # Toggle


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS dnd_log (
        id INTEGER PRIMARY KEY, action TEXT, ts REAL
    )""")


def log_dnd(conn, action: str):
    _ensure_table(conn)
    conn.execute("INSERT INTO dnd_log (action, ts) VALUES (?, ?)", (action, time.time()))
    conn.commit()


def start_dnd_session(conn, duration_minutes: int = 60) -> dict:
    _ensure_table(conn)
    enable_dnd()
    now = time.time()
    conn.execute("INSERT INTO dnd_log (action, ts) VALUES ('start', ?)", (now,))
    conn.commit()
    return {"started": now, "ends": now + duration_minutes * 60}


def end_dnd_session(conn):
    _ensure_table(conn)
    disable_dnd()
    conn.execute("INSERT INTO dnd_log (action, ts) VALUES ('end', ?)", (time.time(),))
    conn.commit()


def get_dnd_stats(conn, days: int = 30) -> dict:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    starts = conn.execute(
        "SELECT COUNT(*) as c FROM dnd_log WHERE action='start' AND ts > ?", (cutoff,)).fetchone()
    ends = conn.execute(
        "SELECT COUNT(*) as c FROM dnd_log WHERE action='end' AND ts > ?", (cutoff,)).fetchone()
    return {"sessions": starts["c"], "completed": ends["c"]}


def is_dnd_active() -> bool:
    """Check if Focus/DND is currently active (best effort)."""
    try:
        r = subprocess.run(
            ["defaults", "read", "com.apple.ncprefs", "dnd_prefs"],
            capture_output=True, text=True, timeout=3)
        return "enabled = 1" in r.stdout.lower()
    except Exception:
        return False
