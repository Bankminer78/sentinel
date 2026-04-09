#!/bin/bash
# Sentinel daemon wrapper — launched by launchd as root.
set -u

export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
LOG=/var/log/sentinel.log

# Resolve the sentinel repo directory (parent of this script's dir).
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

cd "$REPO_DIR" || {
    echo "[sentinel-wrapper] cannot cd to $REPO_DIR" >> "$LOG"
    exit 1
}

# Activate venv if present.
if [ -f "$REPO_DIR/.venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    . "$REPO_DIR/.venv/bin/activate"
elif [ -f "$REPO_DIR/venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    . "$REPO_DIR/venv/bin/activate"
fi

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || command -v python)}"
if [ -z "$PYTHON_BIN" ]; then
    echo "[sentinel-wrapper] no python interpreter found" >> "$LOG"
    exit 1
fi

echo "[sentinel-wrapper] starting sentinel at $(date) using $PYTHON_BIN" >> "$LOG"
exec "$PYTHON_BIN" -m sentinel serve >> "$LOG" 2>&1
