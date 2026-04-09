"""Wi-Fi network detection and logging."""
import subprocess, re, time


def get_current_ssid() -> str:
    """Current Wi-Fi SSID."""
    try:
        r = subprocess.run(
            ["networksetup", "-getairportnetwork", "en0"],
            capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            m = re.search(r"Current Wi-Fi Network: (.+)$", r.stdout.strip())
            if m:
                return m.group(1)
    except Exception:
        pass
    return ""


def get_signal_strength() -> int:
    """Get Wi-Fi signal RSSI (dBm)."""
    try:
        r = subprocess.run(
            ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport",
             "-I"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                if "agrCtlRSSI:" in line:
                    return int(line.split(":", 1)[1].strip())
    except Exception:
        pass
    return 0


def is_wifi_connected() -> bool:
    return bool(get_current_ssid())


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS wifi_log (
        id INTEGER PRIMARY KEY, ssid TEXT, signal INTEGER, ts REAL
    )""")


def log_wifi(conn):
    _ensure_table(conn)
    ssid = get_current_ssid()
    signal = get_signal_strength()
    conn.execute(
        "INSERT INTO wifi_log (ssid, signal, ts) VALUES (?, ?, ?)",
        (ssid, signal, time.time()))
    conn.commit()


def get_wifi_history(conn, limit: int = 100) -> list:
    _ensure_table(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM wifi_log ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()]


def most_common_networks(conn, days: int = 30) -> list:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute("""SELECT ssid, COUNT(*) as count FROM wifi_log
                           WHERE ts > ? AND ssid != '' GROUP BY ssid ORDER BY count DESC""",
                        (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def time_on_network(conn, ssid: str, days: int = 30) -> float:
    """Approximate time on a specific network in hours."""
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    r = conn.execute(
        "SELECT COUNT(*) as c FROM wifi_log WHERE ssid=? AND ts > ?",
        (ssid, cutoff)).fetchone()
    # Assume logged every minute
    return round((r["c"] or 0) / 60, 1)
