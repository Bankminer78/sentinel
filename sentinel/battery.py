"""Battery monitoring and low-power rules."""
import subprocess, re


def get_battery_info() -> dict:
    """Get battery status via pmset on macOS."""
    try:
        r = subprocess.run(
            ["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return {"level": 100, "charging": False, "source": "unknown"}
        text = r.stdout
        # Parse percentage
        level_match = re.search(r"(\d+)%", text)
        level = int(level_match.group(1)) if level_match else 100
        # Charging status
        charging = "charging" in text.lower() or "AC Power" in text
        # Power source
        source = "battery"
        if "AC Power" in text:
            source = "ac"
        return {"level": level, "charging": charging, "source": source}
    except Exception:
        return {"level": 100, "charging": False, "source": "unknown"}


def is_on_battery() -> bool:
    return get_battery_info()["source"] == "battery"


def is_low_battery(threshold: int = 20) -> bool:
    info = get_battery_info()
    return info["source"] == "battery" and info["level"] < threshold


def is_critical_battery(threshold: int = 10) -> bool:
    info = get_battery_info()
    return info["source"] == "battery" and info["level"] < threshold


def get_status_string() -> str:
    info = get_battery_info()
    if info["source"] == "ac":
        return f"Plugged in ({info['level']}%)"
    state = "charging" if info["charging"] else "discharging"
    return f"Battery {info['level']}% ({state})"


def should_conserve() -> bool:
    """Should we switch to power-saving mode?"""
    return is_low_battery(threshold=30)


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS battery_log (
        id INTEGER PRIMARY KEY, level INTEGER, charging INTEGER,
        source TEXT, ts REAL
    )""")


def log_battery(conn):
    _ensure_table(conn)
    import time
    info = get_battery_info()
    conn.execute(
        "INSERT INTO battery_log (level, charging, source, ts) VALUES (?, ?, ?, ?)",
        (info["level"], 1 if info["charging"] else 0, info["source"], time.time()))
    conn.commit()


def get_battery_log(conn, limit: int = 100) -> list:
    _ensure_table(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM battery_log ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()]
