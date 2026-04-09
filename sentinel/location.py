"""Location-based rules — geofencing via Wi-Fi SSID detection."""
import subprocess, re, time


def get_current_wifi_ssid() -> str:
    """Get current Wi-Fi network name on macOS."""
    try:
        # Try airport command first
        r = subprocess.run(
            ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport",
             "-I"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                if "SSID:" in line and "BSSID" not in line:
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    try:
        # Fallback to networksetup
        r = subprocess.run(
            ["networksetup", "-getairportnetwork", "en0"],
            capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            line = r.stdout.strip()
            m = re.search(r"Current Wi-Fi Network: (.+)$", line)
            if m:
                return m.group(1)
    except Exception:
        pass
    return ""


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY, name TEXT, ssid TEXT UNIQUE, is_work INTEGER
    )""")


def add_location(conn, name: str, ssid: str, is_work: bool = False) -> int:
    _ensure_table(conn)
    cur = conn.execute(
        "INSERT OR REPLACE INTO locations (name, ssid, is_work) VALUES (?, ?, ?)",
        (name, ssid, 1 if is_work else 0))
    conn.commit()
    return cur.lastrowid


def get_locations(conn) -> list:
    _ensure_table(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM locations").fetchall()]


def delete_location(conn, location_id: int):
    _ensure_table(conn)
    conn.execute("DELETE FROM locations WHERE id=?", (location_id,))
    conn.commit()


def current_location(conn) -> dict:
    _ensure_table(conn)
    ssid = get_current_wifi_ssid()
    if not ssid:
        return {"name": "unknown", "ssid": "", "is_work": False}
    r = conn.execute("SELECT * FROM locations WHERE ssid=?", (ssid,)).fetchone()
    if r:
        return dict(r)
    return {"name": "unknown", "ssid": ssid, "is_work": False}


def is_at_work(conn) -> bool:
    return current_location(conn).get("is_work", False) == 1 or \
           current_location(conn).get("is_work") is True


def is_at_home(conn) -> bool:
    loc = current_location(conn)
    return not loc.get("is_work") and loc.get("name") != "unknown"


def log_location_change(conn, ssid: str):
    _ensure_table(conn)
    conn.execute("""CREATE TABLE IF NOT EXISTS location_log (
        id INTEGER PRIMARY KEY, ssid TEXT, ts REAL
    )""")
    conn.execute("INSERT INTO location_log (ssid, ts) VALUES (?, ?)",
                 (ssid, time.time()))
    conn.commit()
