#!/bin/bash
# Sentinel LaunchDaemon installer. Run with sudo.
set -euo pipefail

PLIST_LABEL="com.sentinel.daemon"
PLIST_DEST="/Library/LaunchDaemons/${PLIST_LABEL}.plist"
HOSTS_BACKUP="/etc/hosts.sentinel-backup"
LOG_PATH="/var/log/sentinel.log"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_SRC="$SCRIPT_DIR/com.sentinel.daemon.plist"
WRAPPER_SRC="$SCRIPT_DIR/sentinel-wrapper.sh"

err() { echo "error: $*" >&2; exit 1; }
info() { echo "==> $*"; }

if [ "$(id -u)" -ne 0 ]; then
    err "install.sh must be run as root. Try: sudo $0"
fi

[ -f "$PLIST_SRC" ]   || err "missing plist template at $PLIST_SRC"
[ -f "$WRAPPER_SRC" ] || err "missing wrapper script at $WRAPPER_SRC"

chmod 755 "$WRAPPER_SRC" || err "chmod wrapper failed"

info "Backing up /etc/hosts to $HOSTS_BACKUP"
if [ ! -f "$HOSTS_BACKUP" ]; then
    cp /etc/hosts "$HOSTS_BACKUP" || err "failed to back up /etc/hosts"
else
    info "Backup already exists, leaving in place."
fi

info "Ensuring log file $LOG_PATH"
touch "$LOG_PATH" || err "cannot create $LOG_PATH"
chmod 644 "$LOG_PATH" || true

info "Rendering plist with wrapper path $WRAPPER_SRC"
TMP_PLIST="$(mktemp -t sentinel-plist)"
trap 'rm -f "$TMP_PLIST"' EXIT
# Escape characters that might break sed.
ESCAPED_PATH="$(printf '%s\n' "$WRAPPER_SRC" | sed -e 's/[\/&]/\\&/g')"
sed "s|/opt/sentinel/sentinel-wrapper.sh|$ESCAPED_PATH|g" "$PLIST_SRC" > "$TMP_PLIST" || err "sed failed"

info "Installing plist to $PLIST_DEST"
cp "$TMP_PLIST" "$PLIST_DEST" || err "failed to copy plist"
chown root:wheel "$PLIST_DEST" || err "chown failed"
chmod 644 "$PLIST_DEST" || err "chmod failed"

info "Loading LaunchDaemon via launchctl"
# Unload first if already loaded (idempotent).
launchctl unload -w "$PLIST_DEST" 2>/dev/null || true
if ! launchctl load -w "$PLIST_DEST"; then
    err "launchctl load failed — check $LOG_PATH"
fi

cat <<EOF

Sentinel daemon installed successfully.

Next steps:
  1. Configure your Gemini API key:   sentinel config --api-key YOUR_KEY
  2. Install the browser extension from ./extension
  3. Check status:                    launchctl list | grep sentinel
  4. Tail logs:                       tail -f $LOG_PATH

To uninstall (requires completing any active focus session first):
  sudo $SCRIPT_DIR/uninstall.sh
EOF
