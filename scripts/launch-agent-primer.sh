#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_URL="http://127.0.0.1:8765"
HEALTH_URL="${APP_URL}/api/health"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/agent-primer"
LOG_FILE="${STATE_DIR}/server.log"
BROWSER_PROFILE="${STATE_DIR}/browser-profile"
SERVER_PID=""

mkdir -p "$STATE_DIR" "$BROWSER_PROFILE"

is_running() {
  curl --silent --fail --max-time 1 "$HEALTH_URL" >/dev/null 2>&1
}

start_server() {
  cd "$APP_DIR"
  "$APP_DIR/.venv/bin/agent-primer" >>"$LOG_FILE" 2>&1 &
  SERVER_PID="$!"
}

stop_server() {
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}

stop_existing_app_server() {
  pkill -f "$APP_DIR/.venv/bin/agent-primer" >/dev/null 2>&1 || true
}

wait_for_server() {
  for _ in {1..30}; do
    if is_running; then
      return 0
    fi
    sleep 0.2
  done
  return 1
}

browser_command() {
  if [[ -n "${AGENT_PRIMER_BROWSER:-}" ]]; then
    printf '%s\n' "$AGENT_PRIMER_BROWSER"
    return 0
  fi
  for command in chromium google-chrome google-chrome-stable chromium-browser brave-browser microsoft-edge; do
    if command -v "$command" >/dev/null 2>&1; then
      printf '%s\n' "$command"
      return 0
    fi
  done
  return 1
}

open_app_window() {
  local browser
  if browser="$(browser_command)"; then
    "$browser" \
      --app="$APP_URL" \
      --user-data-dir="$BROWSER_PROFILE" \
      --class="AgentPrimer" \
      --no-first-run \
      --disable-first-run-ui \
      >/dev/null 2>&1
    return
  fi
  notify_failure "No Chromium-compatible browser found. Install Chromium to auto-stop the server when the app window closes."
  return 1
}

notify_failure() {
  local message="${1:-Agent Primer did not start. Log: $LOG_FILE}"
  if command -v notify-send >/dev/null 2>&1; then
    notify-send "Agent Primer" "$message"
    return
  fi
  printf '%s\n' "$message" >&2
}

trap stop_server EXIT INT TERM

stop_existing_app_server
start_server

if wait_for_server; then
  open_app_window
else
  notify_failure
  exit 1
fi
