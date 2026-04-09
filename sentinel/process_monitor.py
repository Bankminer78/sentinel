"""Process monitor — CPU/memory usage tracking."""
import subprocess, time


def get_top_processes(limit: int = 10) -> list:
    """Get top processes by CPU usage."""
    try:
        r = subprocess.run(
            ["ps", "-axo", "pid,comm,%cpu,%mem", "-r"],
            capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return []
        lines = r.stdout.strip().splitlines()[1:]  # Skip header
        result = []
        for line in lines[:limit]:
            parts = line.split(None, 3)
            if len(parts) >= 4:
                result.append({
                    "pid": int(parts[0]),
                    "command": parts[1],
                    "cpu": float(parts[2]),
                    "memory": float(parts[3]),
                })
        return result
    except Exception:
        return []


def get_process_by_name(name: str) -> list:
    try:
        r = subprocess.run(
            ["pgrep", "-f", name], capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            return [int(p) for p in r.stdout.split()]
    except Exception:
        pass
    return []


def is_process_running(name: str) -> bool:
    return len(get_process_by_name(name)) > 0


def kill_process(pid: int) -> bool:
    try:
        subprocess.run(["kill", "-9", str(pid)], timeout=3, check=False)
        return True
    except Exception:
        return False


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS process_log (
        id INTEGER PRIMARY KEY, pid INTEGER, command TEXT,
        cpu REAL, memory REAL, ts REAL
    )""")


def log_top_processes(conn, limit: int = 5):
    _ensure_table(conn)
    procs = get_top_processes(limit)
    now = time.time()
    for p in procs:
        conn.execute(
            "INSERT INTO process_log (pid, command, cpu, memory, ts) VALUES (?, ?, ?, ?, ?)",
            (p["pid"], p["command"], p["cpu"], p["memory"], now))
    conn.commit()


def get_process_log(conn, limit: int = 100) -> list:
    _ensure_table(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM process_log ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()]


def cpu_hogs(conn, threshold: float = 50.0, days: int = 7) -> list:
    _ensure_table(conn)
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        "SELECT command, AVG(cpu) as avg_cpu FROM process_log WHERE ts > ? AND cpu > ? GROUP BY command",
        (cutoff, threshold)).fetchall()
    return [dict(r) for r in rows]
