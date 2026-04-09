"""Detect typing/mouse activity as engagement signal."""
import subprocess, time


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS keyboard_log (
        id INTEGER PRIMARY KEY, ts REAL, key_count INTEGER,
        mouse_count INTEGER, window TEXT
    )""")


def get_idle_time_seconds() -> float:
    """How long has the user been idle? Uses ioreg on macOS."""
    try:
        r = subprocess.run(
            ["ioreg", "-c", "IOHIDSystem"], capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return 0.0
        for line in r.stdout.splitlines():
            if "HIDIdleTime" in line:
                # "HIDIdleTime" = <nanoseconds>
                parts = line.split("=")
                if len(parts) == 2:
                    try:
                        ns = int(parts[1].strip())
                        return ns / 1e9
                    except Exception:
                        pass
    except Exception:
        pass
    return 0.0


def is_idle(threshold_seconds: float = 60) -> bool:
    return get_idle_time_seconds() > threshold_seconds


def log_activity(conn, key_count: int, mouse_count: int, window: str = ""):
    _ensure_table(conn)
    conn.execute(
        "INSERT INTO keyboard_log (ts, key_count, mouse_count, window) VALUES (?,?,?,?)",
        (time.time(), key_count, mouse_count, window))
    conn.commit()


def get_typing_rate(conn, minutes: int = 10) -> float:
    """Keys per minute over the last N minutes."""
    _ensure_table(conn)
    cutoff = time.time() - minutes * 60
    r = conn.execute(
        "SELECT COALESCE(SUM(key_count), 0) as total FROM keyboard_log WHERE ts > ?",
        (cutoff,)).fetchone()
    total = r["total"] if r else 0
    return total / minutes if minutes > 0 else 0


def detect_context_switches(conn, window_seconds: int = 300) -> int:
    """Count unique windows visited in the last N seconds."""
    _ensure_table(conn)
    cutoff = time.time() - window_seconds
    rows = conn.execute(
        "SELECT DISTINCT window FROM keyboard_log WHERE ts > ? AND window != ''",
        (cutoff,)).fetchall()
    return len(rows)


def get_activity_summary(conn, minutes: int = 60) -> dict:
    _ensure_table(conn)
    cutoff = time.time() - minutes * 60
    r = conn.execute(
        "SELECT COALESCE(SUM(key_count), 0) as keys, COALESCE(SUM(mouse_count), 0) as mouse "
        "FROM keyboard_log WHERE ts > ?",
        (cutoff,)).fetchone()
    return {
        "keys": r["keys"] if r else 0,
        "mouse": r["mouse"] if r else 0,
        "minutes": minutes,
    }
