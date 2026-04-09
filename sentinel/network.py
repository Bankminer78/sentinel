"""Network-level helpers — DNS, hosts integrity, subnet detection."""
import subprocess, shutil, time, socket
from pathlib import Path

HOSTS_PATH = "/etc/hosts"
_BACKUP_DIR = Path.home() / ".config" / "sentinel" / "hosts_backups"


def flush_dns() -> bool:
    try:
        r = subprocess.run(
            ["dscacheutil", "-flushcache"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def get_current_dns() -> list:
    try:
        r = subprocess.run(
            ["scutil", "--dns"], capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return []
        out = []
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("nameserver[") and ":" in line:
                ip = line.split(":", 1)[1].strip()
                if ip and ip not in out:
                    out.append(ip)
        return out
    except Exception:
        return []


def is_hosts_file_clean() -> bool:
    try:
        content = Path(HOSTS_PATH).read_text()
    except Exception:
        return True
    has_start = "# SENTINEL BLOCK START" in content
    has_end = "# SENTINEL BLOCK END" in content
    return has_start == has_end


def count_hosts_entries() -> int:
    try:
        content = Path(HOSTS_PATH).read_text()
    except Exception:
        return 0
    n = 0
    for line in content.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        n += 1
    return n


def backup_hosts() -> str:
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = _BACKUP_DIR / f"hosts-{stamp}.bak"
    try:
        shutil.copy2(HOSTS_PATH, dest)
        return str(dest)
    except Exception:
        return ""


def restore_hosts_from_backup(backup_path: str) -> bool:
    p = Path(backup_path)
    if not p.exists():
        return False
    try:
        shutil.copy2(p, HOSTS_PATH)
        return True
    except Exception:
        return False


def get_listening_ports() -> list:
    try:
        r = subprocess.run(
            ["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"],
            capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return []
        out = []
        for line in r.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 2:
                continue
            addr = next((p for p in parts if ":" in p and p != ":"), None)
            if not addr:
                continue
            try:
                port = int(addr.rsplit(":", 1)[1])
            except ValueError:
                continue
            out.append({"proc": parts[0], "pid": parts[1], "port": port})
        return out
    except Exception:
        return []


def is_port_available(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()
