#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-9222}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "${SCRIPT_DIR}/port_utils.sh"
APP="$(codex_monitor_find_app || true)"
BUNDLE_ID="$(codex_monitor_app_bundle_id "${APP}" 2>/dev/null || true)"
RESOLVED_PORT="$(codex_monitor_resolve_port "${PORT}")"
if [[ "${RESOLVED_PORT}" != "${PORT}" ]]; then
  echo "Port ${PORT} is unavailable; using ${RESOLVED_PORT} instead." >&2
fi
PORT="${RESOLVED_PORT}"

if [[ -z "${APP}" ]]; then
  echo "Neither ChatGPT.app nor Codex.app could be found in /Applications or ~/Applications." >&2
  exit 1
fi

if codex_monitor_app_running; then
  if [[ -z "${BUNDLE_ID}" ]] || ! osascript -e "tell application id \"${BUNDLE_ID}\" to quit" >/dev/null 2>&1; then
    echo "The Codex app deferred quitting, usually because a response is still active. Retry after it finishes." >&2
    exit 1
  fi
  if ! codex_monitor_wait_for_app_exit 20; then
    echo "The Codex app did not exit; refusing to start a second app instance." >&2
    exit 1
  fi
fi

open "${APP}" --args \
  "--remote-debugging-address=127.0.0.1" \
  "--remote-debugging-port=${PORT}" \
  "--remote-allow-origins=http://127.0.0.1:${PORT}"
echo "Reopened $(basename "${APP}" .app) with local DevTools port ${PORT}."
echo "Then run:"
echo "  python3 ./scripts/context_token_injector.py --port ${PORT}"
