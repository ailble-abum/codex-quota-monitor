#!/usr/bin/env bash

# Local process and DevTools discovery shared by the launcher scripts.  These
# helpers intentionally return plain values; the caller owns retry policy.

codex_monitor_valid_port() {
  [[ "${1:-}" =~ ^[0-9]+$ ]] && ((10#${1} >= 1 && 10#${1} <= 65535))
}

codex_monitor_devtools_target_state() {
  local port="${1:?port required}"
  local mode="${2:?mode required}"
  local script_dir
  codex_monitor_valid_port "${port}" || return 1
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  python3 "${script_dir}/cdp_transport.py" target-state "${port}" "${mode}"
}

codex_monitor_devtools_available() {
  codex_monitor_devtools_target_state "${1:?port required}" owned
}

codex_monitor_devtools_owned() {
  codex_monitor_devtools_target_state "${1:?port required}" owned
}

codex_monitor_devtools_ready() {
  codex_monitor_devtools_target_state "${1:?port required}" ready
}

codex_monitor_find_app() {
  local candidate
  local -a installed=()
  local -a candidates=(
    "/Applications/ChatGPT.app"
    "/Applications/Codex.app"
    "${HOME:-}/Applications/ChatGPT.app"
    "${HOME:-}/Applications/Codex.app"
  )
  if [[ -n "${CODEX_MONITOR_APP_PATH:-}" && -d "${CODEX_MONITOR_APP_PATH}" ]]; then
    printf '%s\n' "${CODEX_MONITOR_APP_PATH}"
    return 0
  fi
  for candidate in "${candidates[@]}"; do
    [[ -d "${candidate}" ]] && installed+=("${candidate}")
  done
  case "${#installed[@]}" in
    0) return 1 ;;
    1) printf '%s\n' "${installed[0]}"; return 0 ;;
  esac
  for candidate in "${installed[@]}"; do
    if [[ -n "$(codex_monitor_process_pid_for_app "${candidate}" 2>/dev/null || true)" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  printf '%s\n' "${installed[0]}"
}

codex_monitor_app_executable() {
  local app="${1:-}"
  local name
  [[ -n "${app}" ]] || app="$(codex_monitor_find_app)" || return 1
  name="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "${app}/Contents/Info.plist" 2>/dev/null || true)"
  printf '%s\n' "${name:-$(basename "${app}" .app)}"
}

codex_monitor_app_bundle_id() {
  local app="${1:-}"
  [[ -n "${app}" ]] || app="$(codex_monitor_find_app)" || return 1
  /usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "${app}/Contents/Info.plist" 2>/dev/null
}

codex_monitor_pid_for_process_path() {
  local process_path="${1:?process path required}"
  ps -axo pid=,command= | awk -v wanted="${process_path}" '
    { pid=$1; sub(/^[[:space:]]*[0-9]+[[:space:]]+/, "", $0)
      if ($0 == wanted || index($0, wanted " ") == 1) { print pid; exit } }'
}

codex_monitor_process_pid_for_app() {
  local app="${1:?app path required}"
  local name="$(basename "${app}" .app)"
  local path="${app}/Contents/MacOS/${name}"
  local pid="$(codex_monitor_pid_for_process_path "${path}" 2>/dev/null || true)"
  [[ -n "${pid}" ]] && { printf '%s\n' "${pid}"; return 0; }
  local fallback="$(codex_monitor_app_executable "${app}" 2>/dev/null || true)"
  [[ -n "${fallback}" && "${fallback}" != "${name}" ]] || return 1
  codex_monitor_pid_for_process_path "${app}/Contents/MacOS/${fallback}"
}

codex_monitor_app_pid() {
  local app="$(codex_monitor_find_app)" || return 1
  codex_monitor_process_pid_for_app "${app}"
}

codex_monitor_app_running() {
  [[ -n "$(codex_monitor_app_pid 2>/dev/null || true)" ]]
}

# Compatibility for scripts from an older installed runtime.
codex_monitor_codex_running() { codex_monitor_app_running; }

codex_monitor_wait_for_app_exit() {
  local attempts="${1:-20}"
  local index
  for ((index=0; index<attempts; index++)); do
    codex_monitor_app_running || return 0
    sleep 0.5
  done
  return 1
}

codex_monitor_port_listening() {
  local port="${1:?port required}"
  codex_monitor_valid_port "${port}" || return 1
  python3 - "${port}" <<'PY'
import socket
import sys
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(0.25)
    raise SystemExit(0 if sock.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)
PY
}

codex_monitor_find_free_port() {
  local start="${1:-9222}"
  local port
  codex_monitor_valid_port "${start}" || start=9222
  for ((port=10#${start}; port<10#${start}+300 && port<=65535; port++)); do
    codex_monitor_port_listening "${port}" || { printf '%s\n' "${port}"; return 0; }
  done
  python3 - <<'PY'
import socket
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
}

codex_monitor_resolve_port() {
  local requested="${1:-9222}"
  codex_monitor_valid_port "${requested}" || return 1
  if ! codex_monitor_port_listening "${requested}"; then
    printf '%s\n' "${requested}"
  elif codex_monitor_devtools_owned "${requested}"; then
    printf '%s\n' "${requested}"
  else
    codex_monitor_find_free_port "$((10#${requested}+1))"
  fi
}

codex_monitor_wait_for_devtools() {
  local port="${1:?port required}"
  local attempts="${2:-30}"
  local index
  for ((index=0; index<attempts; index++)); do
    codex_monitor_devtools_ready "${port}" && return 0
    sleep 1
  done
  return 1
}
