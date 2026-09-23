#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-9222}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/port_utils.sh"

codex_monitor_valid_port "${PORT}" || {
  echo "Invalid DevTools port: ${PORT}" >&2
  exit 2
}
APP="$(codex_monitor_find_app || true)"
if [[ -z "${APP}" ]]; then
  echo "Neither ChatGPT.app nor Codex.app was found." >&2
  exit 1
fi

if codex_monitor_app_running; then
  BUNDLE_ID="$(codex_monitor_app_bundle_id "${APP}" 2>/dev/null || true)"
  if [[ -z "${BUNDLE_ID}" ]] || ! osascript -e "tell application id \"${BUNDLE_ID}\" to quit" >/dev/null 2>&1; then
    echo "The Codex app declined to quit; wait for the active response and retry." >&2
    exit 1
  fi
  if ! codex_monitor_wait_for_app_exit "${CODEX_MONITOR_EXIT_ATTEMPTS:-20}"; then
    echo "The Codex app did not exit; refusing a second instance." >&2
    exit 1
  fi
fi

open "${APP}" --args \
  "--remote-debugging-address=127.0.0.1" \
  "--remote-debugging-port=${PORT}" \
  "--remote-allow-origins=http://127.0.0.1:${PORT}"
echo "Started $(basename "${APP}" .app) with local DevTools port ${PORT}."
