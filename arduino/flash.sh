#!/usr/bin/env bash
#
# flash.sh — stop the illuminatrix service, upload the sketch, restart it.
#
# Usage:
#   ./flash.sh            # compile + upload
#   ./flash.sh -c         # compile only (no upload, service left running)
#   ./flash.sh -v         # verbose: full compiler + avrdude output, shell tracing
#   ./flash.sh -c -v      # flags combine
#
# The service is ALWAYS restarted on exit — even if the upload fails.

set -euo pipefail

# --- Config ----------------------------------------------------------------
SERVICE="illuminatrix"
PORT="/dev/ttyACM0"
FQBN="arduino:avr:mega"
SKETCH="$HOME/Projects/Illuminatrix/python/illuminatrix/arduino/illuminatrix_interface"   # sketch folder
# ---------------------------------------------------------------------------

compile_only=false
verbose=false
for arg in "$@"; do
  case "$arg" in
    -c) compile_only=true ;;
    -v) verbose=true ;;
    *)  printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
  esac
done

# Extra flags passed to arduino-cli when -v is set.
CLI_FLAGS=()
$verbose && CLI_FLAGS+=(--verbose)
# Shell tracing: echo each command as it runs.
$verbose && set -x

log()  { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }
fail() { printf '\n\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

command -v arduino-cli >/dev/null || fail "arduino-cli not found on PATH"
[[ -d "$SKETCH" ]]                || fail "sketch folder not found: $SKETCH"

# Always bring the service back up when the script exits, for any reason.
service_was_active=false
restore_service() {
  if $service_was_active; then
    log "Restarting $SERVICE service"
    sudo systemctl start "$SERVICE"
  fi
}
trap restore_service EXIT

# --- Compile ---------------------------------------------------------------
log "Compiling $SKETCH"
arduino-cli compile "${CLI_FLAGS[@]}" --fqbn "$FQBN" "$SKETCH"

if $compile_only; then
  log "Compile-only mode — done."
  exit 0
fi

# --- Free the port ---------------------------------------------------------
if systemctl is-active --quiet "$SERVICE"; then
  service_was_active=true
  log "Stopping $SERVICE to free $PORT"
  sudo systemctl stop "$SERVICE"
  sleep 1   # let the graceful shutdown close the port + settle DTR
fi

# --- Upload ----------------------------------------------------------------
log "Uploading to $PORT"
arduino-cli upload "${CLI_FLAGS[@]}" -p "$PORT" --fqbn "$FQBN" "$SKETCH"

log "Upload complete."
