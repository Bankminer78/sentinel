#!/bin/bash
# Sentinel LaunchDaemon uninstaller. Run with sudo.
set -u

PLIST_LABEL="com.sentinel.daemon"
PLIST_DEST="/Library/LaunchDaemons/${PLIST_LABEL}.plist"
HOSTS_BACKUP="/etc/hosts.sentinel-backup"

err() { echo "error: $*" >&2; exit 1; }
info() { echo "==> $*"; }

if [ "$(id -u)" -ne 0 ]; then
    err "uninstall.sh must be run as root. Try: sudo $0"
fi

info "Unloading LaunchDaemon"
if [ -f "$PLIST_DEST" ]; then
    launchctl unload -w "$PLIST_DEST" 2>/dev/null || true
    info "Removing $PLIST_DEST"
    rm -f "$PLIST_DEST" || err "failed to remove plist"
else
    info "No plist at $PLIST_DEST, skipping"
fi

if [ -f "$HOSTS_BACKUP" ]; then
    info "Restoring /etc/hosts from $HOSTS_BACKUP"
    cp "$HOSTS_BACKUP" /etc/hosts || err "failed to restore /etc/hosts"
    rm -f "$HOSTS_BACKUP"
    # Flush DNS
    dscacheutil -flushcache 2>/dev/null || true
    killall -HUP mDNSResponder 2>/dev/null || true
else
    info "No hosts backup found, leaving /etc/hosts as-is"
fi

echo
echo "Sentinel daemon uninstalled successfully."
