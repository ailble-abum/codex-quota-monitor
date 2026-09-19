#!/usr/bin/env bash

codex_monitor_devtools_available() {
  local port="${1:?port required}"
  curl --max-time 0.4 -fsS "http://127.0.0.1:${port}/json" >/dev/null 2>&1
}

codex_monitor_devtools_target_state() {
  local port="${1:?port required}"
  local mode="${2:?mode required}"
  python3 - "${port}" "${mode}" <<'PY'
import json
import sys
import urllib.parse
import urllib.request

port = int(sys.argv[1])
mode = sys.argv[2]
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=0.5) as response:
        targets = json.load(response)
except (OSError, ValueError):
    raise SystemExit(1)

for target in targets if isinstance(targets, list) else []:
    if target.get("type") != "page":
        continue
    title = str(target.get("title") or "").lower()
    url = str(target.get("url") or "").lower()
    decoded_url = urllib.parse.unquote(url)
    owned = url.startswith("app://") and (
        "codex" in title
        or "chatgpt" in title
        or url.startswith("app://codex/")
        or url.startswith("app://-/index.html")
    )
    if not owned:
        continue
    if mode == "owned":
        raise SystemExit(0)
    if mode == "ready" and "initialroute=" not in decoded_url and "avatar-overlay" not in decoded_url:
        raise SystemExit(0)
raise SystemExit(1)
PY
}

codex_monitor_devtools_owned() {
  codex_monitor_devtools_target_state "${1:?port required}" owned
}

codex_monitor_devtools_ready() {
  codex_monitor_devtools_target_state "${1:?port required}" ready
}

codex_monitor_find_app() {
  local candidate
  local installed=()
  local candidates=(
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
    if [[ -d "${candidate}" ]]; then
      installed+=("${candidate}")
    fi
  done
  if [[ "${#installed[@]}" -eq 0 ]]; then
    return 1
  fi
  if [[ "${#installed[@]}" -eq 1 ]]; then
    printf '%s\n' "${installed[0]}"
    return 0
  fi

  # Users can temporarily have both bundles after an upgrade. Only then is a
  # process scan needed to decide which installation currently owns the UI.
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
  local executable
  if [[ -z "${app}" ]]; then
    app="$(codex_monitor_find_app)" || return 1
  fi
  executable="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "${app}/Contents/Info.plist" 2>/dev/null || true)"
  if [[ -z "${executable}" ]]; then
    executable="$(basename "${app}" .app)"
  fi
  printf '%s\n' "${executable}"
}

codex_monitor_app_bundle_id() {
  local app="${1:-}"
  if [[ -z "${app}" ]]; then
    app="$(codex_monitor_find_app)" || return 1
  fi
  /usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "${app}/Contents/Info.plist" 2>/dev/null
}

codex_monitor_app_pid() {
  local app
  app="$(codex_monitor_find_app)" || return 1
  codex_monitor_process_pid_for_app "${app}"
}

codex_monitor_process_pid_for_app() {
  local app="${1:?app path required}"
  local executable
  local fallback_executable
  local pid
  local process_path
  executable="$(basename "${app}" .app)"
  process_path="${app}/Contents/MacOS/${executable}"

  # Match the main bundle executable only. Renderer and app-server children also
  # contain "Codex" in their command lines and must not count as the app itself.
  pid="$(codex_monitor_pid_for_process_path "${process_path}")"
  if [[ -n "${pid}" ]]; then
    printf '%s\n' "${pid}"
    return 0
  fi

  # Most app bundles use the bundle name as the executable, avoiding a plist
  # read on every poll. Keep a fallback for renamed or future app bundles.
  fallback_executable="$(codex_monitor_app_executable "${app}")" || return 1
  if [[ "${fallback_executable}" == "${executable}" ]]; then
    return 1
  fi
  codex_monitor_pid_for_process_path "${app}/Contents/MacOS/${fallback_executable}"
}

codex_monitor_pid_for_process_path() {
  local process_path="${1:?process path required}"
  ps -axo pid=,command= | awk -v process_path="${process_path}" '
    {
      pid = $1
      sub(/^[[:space:]]*[0-9]+[[:space:]]+/, "", $0)
      if ($0 == process_path || index($0, process_path " ") == 1) {
        print pid
        exit
      }
    }
  '
}

codex_monitor_app_running() {
  [[ -n "$(codex_monitor_app_pid 2>/dev/null || true)" ]]
}

# Kept for scripts installed by older plugin releases.
codex_monitor_codex_running() {
  codex_monitor_app_running
}

codex_monitor_wait_for_app_exit() {
  local attempts="${1:-20}"
  local index
  for ((index=0; index<attempts; index++)); do
    if ! codex_monitor_app_running; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

codex_monitor_port_listening() {
  local port="${1:?port required}"
  python3 - "${port}" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(0.2)
    raise SystemExit(0 if sock.connect_ex(("127.0.0.1", port)) == 0 else 1)
PY
}

codex_monitor_find_free_port() {
  local start="${1:-9222}"
  local port
  for ((port=start; port<start+300; port++)); do
    if ! codex_monitor_port_listening "${port}"; then
      echo "${port}"
      return 0
    fi
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
  if codex_monitor_port_listening "${requested}"; then
    # Reuse the port only when it belongs to this app. A browser or another
    # Electron app may expose a perfectly valid /json endpoint on the same port.
    if codex_monitor_devtools_owned "${requested}"; then
      echo "${requested}"
      return 0
    fi
    codex_monitor_find_free_port "$((requested + 1))"
    return 0
  fi
  echo "${requested}"
}

codex_monitor_wait_for_devtools() {
  local port="${1:?port required}"
  local attempts="${2:-30}"
  local index
  for ((index=0; index<attempts; index++)); do
    if codex_monitor_devtools_ready "${port}"; then
      return 0
    fi
    sleep 1
  done
  return 1
}
