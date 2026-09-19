#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-9222}"
REOPEN_AFTER_QUIT="${CODEX_MONITOR_REOPEN_AFTER_QUIT:-1}"
APP_POLL_INTERVAL="${CODEX_MONITOR_APP_POLL_INTERVAL:-15}"
if [[ "${2:-}" == "--no-reopen-after-quit" ]]; then
  REOPEN_AFTER_QUIT="0"
fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/port_utils.sh"

REQUESTED_PORT="${PORT}"
PORT="$(codex_monitor_resolve_port "${REQUESTED_PORT}")"
LAST_RELAUNCH_PID=""

wait_for_app_if_needed() {
  if [[ "${REOPEN_AFTER_QUIT}" != "0" ]] || codex_monitor_app_running; then
    return 0
  fi
  echo "Codex is not running; Monitor will wait for the next manual launch."
  until codex_monitor_app_running; do
    # A LaunchAgent can remain alive for days while the app is closed. A modest
    # interval keeps automatic startup responsive without continuously forking
    # process and plist inspection commands in the background.
    sleep "${APP_POLL_INTERVAL}"
  done
}

ensure_devtools() {
  local observed_pid
  if codex_monitor_devtools_ready "${PORT}"; then
    return 0
  fi

  wait_for_app_if_needed
  PORT="$(codex_monitor_resolve_port "${REQUESTED_PORT}")"
  if codex_monitor_devtools_ready "${PORT}"; then
    return 0
  fi

  observed_pid="$(codex_monitor_app_pid 2>/dev/null || true)"
  if [[ -n "${observed_pid}" && "${observed_pid}" == "${LAST_RELAUNCH_PID}" ]]; then
    return 1
  fi

  if ! "${SCRIPT_DIR}/reopen_codex_with_debug.sh" "${PORT}"; then
    LAST_RELAUNCH_PID="${observed_pid}"
    return 1
  fi
  codex_monitor_wait_for_devtools "${PORT}" 30 || true

  # Remember the replacement PID too. If this app build rejects CDP flags, the
  # agent waits for a genuinely new launch instead of repeatedly restarting it.
  LAST_RELAUNCH_PID="$(codex_monitor_app_pid 2>/dev/null || true)"
  codex_monitor_devtools_ready "${PORT}"
}

while true; do
  if ensure_devtools; then
    if ! python3 "${SCRIPT_DIR}/context_token_injector.py" --port "${PORT}" --quiet; then
      python3 "${SCRIPT_DIR}/injector_status.py" error InjectorExited || true
    fi
  else
    python3 "${SCRIPT_DIR}/injector_status.py" error DevToolsUnavailable || true
    sleep 15
  fi
  sleep 3
done
