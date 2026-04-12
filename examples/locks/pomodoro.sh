#!/usr/bin/env bash
# sentinel: name="Pomodoro"
# sentinel: description="Four 25/5 cycles. Updates the sidebar countdown each second."
set -euo pipefail

NAME="${SENTINEL_LOCK_NAME:-pomodoro}"
WORK=$((25 * 60))
BREAK=$((5 * 60))
CYCLES=4

notify() {
  osascript -e "display notification \"$1\" with title \"Pomodoro\"" 2>/dev/null || true
}

countdown() {
  local label="$1"
  local seconds="$2"
  local end=$(($(date +%s) + seconds))
  while [ "$(date +%s)" -lt "$end" ]; do
    sentinel check "$NAME" || { sentinel log "$NAME" stopped; exit 0; }
    local left=$((end - $(date +%s)))
    sentinel status "$NAME" "$label · $((left / 60))m $((left % 60))s left"
    sleep 1
  done
}

sentinel log "$NAME" started
notify "Starting $CYCLES cycles"

for cycle in $(seq 1 $CYCLES); do
  notify "Cycle $cycle: 25 min focus"
  countdown "cycle $cycle work" "$WORK"
  sentinel log "$NAME" work_complete "{\"cycle\":$cycle}"

  if [ "$cycle" -lt "$CYCLES" ]; then
    notify "Break: 5 min"
    countdown "cycle $cycle break" "$BREAK"
    sentinel log "$NAME" break_complete "{\"cycle\":$cycle}"
  fi
done

sentinel log "$NAME" complete
notify "All cycles done!"
