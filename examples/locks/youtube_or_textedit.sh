#!/usr/bin/env bash
# sentinel: name="YouTube or TextEdit"
# sentinel: description="Lock to YouTube and TextEdit for 2 minutes. Three sustained violations and TextEdit steals focus."
set -euo pipefail

NAME="${SENTINEL_LOCK_NAME:-youtube_or_textedit}"
DURATION=120
THRESHOLD=3
END=$(($(date +%s) + DURATION))
VIOLATIONS=0
ALLOWED_APPS=("TextEdit" "Sentinel")
BROWSERS=("Google Chrome" "Safari" "Arc" "Brave Browser" "Microsoft Edge" "Firefox")

front_app() {
  osascript -e 'tell application "System Events" to name of (process 1 where frontmost is true)' 2>/dev/null
}

active_url() {
  osascript -e "tell application \"$1\" to URL of active tab of front window" 2>/dev/null || true
}

is_browser() {
  for b in "${BROWSERS[@]}"; do [ "$1" = "$b" ] && return 0; done
  return 1
}

is_allowed() {
  local app="$1"
  for a in "${ALLOWED_APPS[@]}"; do [ "$app" = "$a" ] && return 0; done
  if is_browser "$app"; then
    local url
    url=$(active_url "$app")
    [[ "$url" == *"youtube.com"* ]] && return 0
  fi
  return 1
}

notify() {
  osascript -e "display notification \"$1\" with title \"YouTube or TextEdit\"" 2>/dev/null || true
}

notify "Locked for 2 minutes"
sentinel log "$NAME" engaged "{\"duration_s\":$DURATION,\"threshold\":$THRESHOLD}"

while [ "$(date +%s)" -lt "$END" ]; do
  sentinel check "$NAME" || { sentinel log "$NAME" stopped; exit 0; }

  REMAINING=$((END - $(date +%s)))
  sentinel status "$NAME" "${REMAINING}s left · violations $VIOLATIONS"

  APP=$(front_app)
  if is_allowed "$APP"; then
    VIOLATIONS=0
  else
    VIOLATIONS=$((VIOLATIONS + 1))
    sentinel log "$NAME" violation "{\"app\":\"$APP\",\"count\":$VIOLATIONS}"
    if [ "$VIOLATIONS" -ge "$THRESHOLD" ]; then
      open -a TextEdit
      VIOLATIONS=0
    fi
  fi
  sleep 2
done

sentinel log "$NAME" expired
notify "Done — you're free"
