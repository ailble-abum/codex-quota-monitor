#!/usr/bin/env bash
set -euo pipefail

REQUESTED_PORT="${1:-9222}"
REOPEN_AFTER_QUIT="${CODEX_MONITOR_REOPEN_AFTER_QUIT:-1}"
POLL_INTERVAL="${CODEX_MONITOR_APP_POLL_INTERVAL:-15}"
if [[ "${2:-}" == "--no-reopen-after-quit" ]]; then
  REOPEN_AFTER_QUIT=0
fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/port_utils.sh"

codex_monitor_valid_port "${REQUESTED_PORT}" || {
  echo "Invalid DevTools port: ${REQUESTED_PORT}" >&2
  exit 2
}
PORT="$(codex_monitor_resolve_port "${REQUESTED_PORT}")"
LAST_RELAUNCH_PID=""

wait_for_app() {
  if codex_monitor_app_running; then
    return 0
  fi
  if [[ "${REOPEN_AFTER_QUIT}" != "0" ]]; then
    return 0
  fi
  echo "Codex is not running; waiting for a manual launch."
  until codex_monitor_app_running; do
    sleep "${POLL_INTERVAL}"
  done
}

ensure_devtools() {
  local observed_pid
  codex_monitor_devtools_ready "${PORT}" && return 0
  wait_for_app
  PORT="$(codex_monitor_resolve_port "${REQUESTED_PORT}")"
  codex_monitor_devtools_ready "${PORT}" && return 0

  observed_pid="$(codex_monitor_app_pid 2>/dev/null || true)"
  if [[ "${observed_pid}" == "${LAST_RELAUNCH_PID}" && -n "${observed_pid}" ]]; then
    return 1
  fi
  if [[ "${REOPEN_AFTER_QUIT}" == "0" ]]; then
    codex_monitor_wait_for_devtools "${PORT}" "${CODEX_MONITOR_READY_ATTEMPTS:-10}"
    return $?
  fi

  if ! "${SCRIPT_DIR}/reopen_codex_with_debug.sh" "${PORT}"; then
    LAST_RELAUNCH_PID="${observed_pid}"
    return 1
  fi
  LAST_RELAUNCH_PID="$(codex_monitor_app_pid 2>/dev/null || true)"
  codex_monitor_wait_for_devtools "${PORT}" "${CODEX_MONITOR_READY_ATTEMPTS:-30}"
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
