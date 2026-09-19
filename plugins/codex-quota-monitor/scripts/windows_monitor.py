"""Bounded Windows adapter for the Codex quota monitor.

The adapter owns only its own worker and its own per-user scheduled task.  It
never launches, relaunches, or terminates Codex.  The worker waits for a
loopback CDP endpoint, starts the existing ``context_token_injector.py`` with
the current Python interpreter, and starts it again after a disconnect.

``manage(action)`` is intentionally importable on every platform.  On a
non-Windows host it only returns a command plan; it does not invoke
``schtasks`` or any other Windows command.  This keeps the planning and
validation tests runnable on macOS/Linux while leaving execution to Windows.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Callable, Mapping, Sequence
import urllib.error
import urllib.request


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PORT = 9222
DEFAULT_POLL_INTERVAL = 5.0
DEFAULT_RESTART_DELAY = 2.0
DEFAULT_STOP_TIMEOUT = 8.0
STALE_AFTER_SECONDS = 120
TASK_NAME = "CodexQuotaMonitor"
MUTEX_NAME = r"Local\CodexQuotaMonitor.Worker"
ACTION_NAMES = (
    "install",
    "start",
    "stop",
    "status",
    "doctor",
    "show",
    "reset-position",
)
SCRIPT_SUFFIXES = frozenset({".py", ".ps1", ".sh", ".swift"})


class WindowsAdapterError(RuntimeError):
    """An expected adapter operation failed."""


class AdapterPaths:
    """Files owned by this adapter below one runtime root."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.scripts = self.root / "scripts"
        self.snapshot = self.root / "snapshot.json"
        self.history = self.root / "history.html"
        self.history_json = self.root / "history.json"
        self.notification = self.root / "notification.json"
        self.worker_state = self.root / "worker.json"
        self.stop_request = self.root / "worker.stop"

    def as_dict(self) -> dict[str, str]:
        return {
            "root": str(self.root),
            "scripts": str(self.scripts),
            "snapshot": str(self.snapshot),
            "history": str(self.history),
            "history_json": str(self.history_json),
            "notification": str(self.notification),
            "worker_state": str(self.worker_state),
            "stop_request": str(self.stop_request),
        }


def _environment(environ: Mapping[str, str] | None = None) -> Mapping[str, str]:
    return os.environ if environ is None else environ


def local_app_data(environ: Mapping[str, str] | None = None) -> Path:
    """Return the per-user Windows local application-data directory.

    ``LOCALAPPDATA`` is the normal path.  The home-directory fallback is only
    for unusual Windows shells where the variable was removed; it also makes
    plan generation deterministic in tests.
    """

    value = _environment(environ).get("LOCALAPPDATA")
    if value:
        return Path(value).expanduser()
    return Path.home() / "AppData" / "Local"


def runtime_root(
    environ: Mapping[str, str] | None = None,
    root: str | os.PathLike[str] | None = None,
) -> Path:
    """Return ``%LOCALAPPDATA%/CodexQuotaMonitor`` unless overridden."""

    if root is not None:
        return Path(root)
    if environ is None:
        # The shared platform module is the source of truth for the rest of
        # the plugin.  Keep a local fallback so this adapter remains
        # importable from an isolated source checkout.
        try:
            from platform_paths import runtime_root as shared_runtime_root
        except ImportError:
            pass
        else:
            return Path(shared_runtime_root())
    return local_app_data(environ) / "CodexQuotaMonitor"


def adapter_paths(
    environ: Mapping[str, str] | None = None,
    root: str | os.PathLike[str] | None = None,
) -> AdapterPaths:
    return AdapterPaths(runtime_root(environ=environ, root=root))


def configured_port(
    port: int | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    """Resolve and validate the loopback CDP port.

    The explicit argument is useful to the worker and tests.  Normal users
    configure ``CODEX_MONITOR_PORT``; its default is 9222.
    """

    value: int | str = port if port is not None else _environment(environ).get("CODEX_MONITOR_PORT", DEFAULT_PORT)
    if isinstance(value, bool):
        raise ValueError("CODEX_MONITOR_PORT must be an integer port")
    try:
        resolved = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("CODEX_MONITOR_PORT must be an integer port") from exc
    if not 1 <= resolved <= 65535:
        raise ValueError("CODEX_MONITOR_PORT must be between 1 and 65535")
    return resolved


def cdp_targets_url(port: int | str) -> str:
    return f"http://127.0.0.1:{configured_port(port)}/json"


def read_cdp_targets(
    port: int | str,
    opener: Callable[..., Any] | None = None,
) -> list[dict[str, Any]]:
    """Read only the local CDP target list; no remote endpoint is contacted."""

    open_url = opener or urllib.request.urlopen
    with open_url(cdp_targets_url(port), timeout=2) as response:
        raw = response.read().decode("utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def find_cdp_port(
    port: int | str | None = None,
    environ: Mapping[str, str] | None = None,
    opener: Callable[..., Any] | None = None,
) -> int | None:
    """Return the configured port when its loopback CDP endpoint is present.

    There is deliberately no port scan and no app launch.  The environment
    variable identifies the one endpoint the monitor is allowed to inspect.
    """

    resolved = configured_port(port, environ)
    try:
        read_cdp_targets(resolved, opener=opener)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, urllib.error.URLError):
        return None
    return resolved


def iter_plugin_scripts(source_dir: str | os.PathLike[str] | None = None) -> list[Path]:
    """List source files that belong in the installed scripts directory."""

    source = Path(source_dir) if source_dir is not None else SCRIPT_DIR
    if not source.is_dir():
        raise FileNotFoundError(f"Plugin scripts directory not found: {source}")
    files: list[Path] = []
    for path in sorted(source.rglob("*")):
        relative_parts = path.relative_to(source).parts
        if not path.is_file() or path.suffix.lower() not in SCRIPT_SUFFIXES:
            continue
        if any(part == "__pycache__" for part in relative_parts):
            continue
        files.append(path)
    return files


def copy_plugin_scripts(
    destination: str | os.PathLike[str],
    source_dir: str | os.PathLike[str] | None = None,
) -> list[Path]:
    """Copy the plugin's script files into an installed runtime directory."""

    source = Path(source_dir) if source_dir is not None else SCRIPT_DIR
    target_root = Path(destination)
    target_root.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for source_path in iter_plugin_scripts(source):
        target = target_root / source_path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        # This matters when an already-installed worker is asked to install
        # itself again.  shutil.copy2 would otherwise raise SameFileError.
        if source_path.resolve() == target.resolve():
            continue
        shutil.copy2(source_path, target)
        copied.append(target)
    return copied


def current_python(executable: str | os.PathLike[str] | None = None) -> str:
    """Select the interpreter used to install and run the worker."""

    if executable is not None and str(executable):
        return str(executable)
    return sys.executable or "python.exe"


def build_worker_command(
    python_executable: str | os.PathLike[str] | None = None,
    worker_script: str | os.PathLike[str] | None = None,
) -> list[str]:
    script = Path(worker_script) if worker_script is not None else SCRIPT_DIR / "windows_monitor.py"
    return [current_python(python_executable), str(script), "run"]


def build_injector_command(
    port: int | str,
    python_executable: str | os.PathLike[str] | None = None,
    injector_script: str | os.PathLike[str] | None = None,
) -> list[str]:
    script = (
        Path(injector_script)
        if injector_script is not None
        else SCRIPT_DIR / "context_token_injector.py"
    )
    return [current_python(python_executable), str(script), "--port", str(configured_port(port))]


def build_tray_command(
    powershell_executable: str | os.PathLike[str] = "powershell.exe",
    tray_script: str | os.PathLike[str] | None = None,
) -> list[str]:
    """Build the optional tray command for a caller that owns its process."""

    script = Path(tray_script) if tray_script is not None else SCRIPT_DIR / "windows_tray.ps1"
    return [
        str(powershell_executable),
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
    ]


def tray_environment(
    python_executable: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return the tray environment, pinning helper actions to this Python."""

    result = dict(os.environ)
    if environ is not None:
        result.update(environ)
    result["CODEX_MONITOR_PYTHON"] = current_python(python_executable)
    return result


def build_task_create_command(
    task_name: str = TASK_NAME,
    python_executable: str | os.PathLike[str] | None = None,
    worker_script: str | os.PathLike[str] | None = None,
) -> list[str]:
    """Build a non-admin, current-user ONLOGON task registration command."""

    task_action = subprocess.list2cmdline(build_worker_command(python_executable, worker_script))
    return [
        "schtasks.exe",
        "/Create",
        "/TN",
        task_name,
        "/SC",
        "ONLOGON",
        "/TR",
        task_action,
        "/RL",
        "LIMITED",
        "/F",
    ]


def build_task_start_command(task_name: str = TASK_NAME) -> list[str]:
    return ["schtasks.exe", "/Run", "/TN", task_name]


def build_task_enable_command(task_name: str = TASK_NAME) -> list[str]:
    return ["schtasks.exe", "/Change", "/TN", task_name, "/ENABLE"]


def build_task_disable_command(task_name: str = TASK_NAME) -> list[str]:
    return ["schtasks.exe", "/Change", "/TN", task_name, "/DISABLE"]


def build_task_query_command(task_name: str = TASK_NAME) -> list[str]:
    return ["schtasks.exe", "/Query", "/TN", task_name, "/FO", "LIST", "/V"]


def powershell_quote(value: str | os.PathLike[str]) -> str:
    """Quote a value for a PowerShell command using single-quote escaping."""

    return "'" + str(value).replace("'", "''") + "'"


def codex_launch_instructions(
    port: int | str | None = None,
    app_path: str | os.PathLike[str] | None = None,
) -> str:
    """Return manual launch instructions when CDP is not available."""

    resolved_port = configured_port(port)
    app = str(app_path) if app_path else r"C:\Path\To\Codex.exe"
    lines = [
        "The monitor does not reopen Codex automatically.",
        "Close any existing Codex instance and launch it manually from PowerShell with:",
        f"$env:CODEX_MONITOR_PORT = {powershell_quote(resolved_port)}",
        f"$env:CODEX_MONITOR_APP_PATH = {powershell_quote(app)}",
        "& $env:CODEX_MONITOR_APP_PATH --remote-debugging-port=$env:CODEX_MONITOR_PORT --remote-debugging-address=127.0.0.1",
        "If Codex.exe is elsewhere, set CODEX_MONITOR_APP_PATH to its full path first.",
    ]
    return "\n".join(lines)


def notification_is_fresh(notification: Mapping[str, Any] | None, now: float | None = None) -> bool:
    """Return whether a Windows notification is eligible for tray delivery."""

    if not isinstance(notification, Mapping):
        return False
    try:
        timestamp = float(notification.get("at"))
    except (TypeError, ValueError):
        return False
    current = time.time() if now is None else float(now)
    return current - timestamp <= STALE_AFTER_SECONDS


def notification_text(notification: Mapping[str, Any] | None) -> str | None:
    if not isinstance(notification, Mapping):
        return None
    message = notification.get("message")
    return message if isinstance(message, str) and message.strip() else None


def find_codex_app_path(environ: Mapping[str, str] | None = None) -> Path | None:
    """Find a configured or conventional executable for diagnostics only."""

    env = _environment(environ)
    configured = env.get("CODEX_MONITOR_APP_PATH")
    if configured:
        path = Path(configured).expanduser()
        return path if path.is_file() else None

    local = local_app_data(env)
    candidates = [
        local / "Programs" / "Codex" / "Codex.exe",
        local / "Programs" / "ChatGPT" / "ChatGPT.exe",
    ]
    program_files = env.get("ProgramFiles")
    if program_files:
        candidates.extend(
            [
                Path(program_files) / "Codex" / "Codex.exe",
                Path(program_files) / "ChatGPT" / "ChatGPT.exe",
            ]
        )
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def build_management_plan(
    action: str,
    *,
    environ: Mapping[str, str] | None = None,
    source_dir: str | os.PathLike[str] | None = None,
    root: str | os.PathLike[str] | None = None,
    python_executable: str | os.PathLike[str] | None = None,
    task_name: str = TASK_NAME,
) -> dict[str, Any]:
    """Build an action plan without creating files or running Windows tools."""

    if action not in ACTION_NAMES:
        raise ValueError(f"Unsupported Windows monitor action: {action}")

    paths = adapter_paths(environ=environ, root=root)
    source = Path(source_dir) if source_dir is not None else SCRIPT_DIR
    worker = paths.scripts / "windows_monitor.py"
    copy_files: list[str] = []
    if action == "install":
        copy_files = [str(path.relative_to(source)) for path in iter_plugin_scripts(source)]

    commands: list[list[str]] = []
    if action == "install":
        commands.append(build_task_create_command(task_name, python_executable, worker))
    elif action == "start":
        commands.append(build_task_enable_command(task_name))
        commands.append(build_task_start_command(task_name))
    elif action == "stop":
        commands.append(build_task_disable_command(task_name))
    elif action in {"status", "doctor"}:
        commands.append(build_task_query_command(task_name))

    resolved_port = configured_port(environ=environ)
    return {
        "action": action,
        "task_name": task_name,
        "paths": paths.as_dict(),
        "copy_files": copy_files,
        "commands": commands,
        "worker_command": build_worker_command(python_executable, worker),
        "tray_command": build_tray_command(tray_script=paths.scripts / "windows_tray.ps1"),
        "tray_environment": {"CODEX_MONITOR_PYTHON": current_python(python_executable)},
        "cooperative_stop": action == "stop",
        "stop_timeout": DEFAULT_STOP_TIMEOUT,
        "port": resolved_port,
        "helper": str(paths.scripts / "context_token_injector.py"),
        "launch_instructions": codex_launch_instructions(resolved_port),
    }


def run_command(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run one owned Windows command without a shell."""

    return subprocess.run(list(args), capture_output=True, text=True)


def _returncode(result: Any) -> int:
    value = getattr(result, "returncode", 1)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 1


def _output(result: Any) -> str:
    stdout = str(getattr(result, "stdout", "") or "")
    stderr = str(getattr(result, "stderr", "") or "")
    return "\n".join(part for part in (stdout.strip(), stderr.strip()) if part)


def _command_result(result: Any) -> dict[str, Any]:
    return {
        "returncode": _returncode(result),
        "stdout": str(getattr(result, "stdout", "") or ""),
        "stderr": str(getattr(result, "stderr", "") or ""),
    }


def task_state(output: str) -> str:
    """Normalize common ``schtasks /FO LIST`` states."""

    lowered = output.lower()
    if "running" in lowered:
        return "running"
    if "ready" in lowered:
        return "ready"
    if "disabled" in lowered:
        return "disabled"
    if "could not" in lowered or "error" in lowered or "not found" in lowered:
        return "not-installed"
    return "unknown"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def _write_worker_state(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps({"pid": os.getpid(), "startedAt": time.time()}),
        encoding="utf-8",
    )
    temporary.replace(path)


def _clear_worker_state(path: Path) -> None:
    state = _read_json(path)
    if state and state.get("pid") != os.getpid():
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def wait_for_worker_exit(
    state_path: str | os.PathLike[str],
    timeout: float = DEFAULT_STOP_TIMEOUT,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> bool:
    """Wait for this adapter's cooperative worker shutdown, without killing."""

    path = Path(state_path)
    deadline = time.monotonic() + max(0.0, timeout)
    while path.exists() and time.monotonic() < deadline:
        _sleep(min(0.25, max(0.0, deadline - time.monotonic())), sleep_fn)
    return not path.exists()


def _pid_alive(pid: Any) -> bool:
    """Check an owned worker PID without sending it a signal on Windows."""

    if os.name != "nt":
        # The status file is advisory on non-Windows hosts.  In particular,
        # do not use a signal-based probe: it is not a portable,
        # side-effect-free probe on Windows.
        return False
    try:
        value = int(pid)
    except (TypeError, ValueError):
        return False
    if value <= 0:
        return False

    process_query_limited_information = 0x1000
    still_active = 259
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        kernel32.GetExitCodeProcess.restype = ctypes.c_bool
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_bool
        handle = kernel32.OpenProcess(
            process_query_limited_information,
            False,
            value,
        )
        if not handle:
            return False
        exit_code = ctypes.c_uint32()
        try:
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    except (AttributeError, OSError, TypeError, ValueError):
        return False


class NamedMutex:
    """Small wrapper around an adapter-owned Windows named mutex."""

    ERROR_ALREADY_EXISTS = 183

    def __init__(self, name: str = MUTEX_NAME, platform_name: str | None = None):
        self.name = name
        self.platform_name = platform_name or os.name
        self.handle: Any = None

    def acquire(self) -> bool:
        if self.platform_name != "nt":
            return True
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_bool
        handle = kernel32.CreateMutexW(None, False, self.name)
        if not handle:
            error = ctypes.get_last_error()
            raise OSError(error, f"CreateMutexW failed for {self.name}")
        if ctypes.get_last_error() == self.ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        self.handle = handle
        return True

    def release(self) -> None:
        if self.handle is None:
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_bool
        kernel32.CloseHandle(self.handle)
        self.handle = None


def _stop_requested(path: Path) -> bool:
    return path.exists()


def _sleep(seconds: float, sleep_fn: Callable[[float], None]) -> None:
    sleep_fn(max(0.0, seconds))


def _wait_for_injector(
    process: Any,
    stop_file: Path,
    sleep_fn: Callable[[float], None],
    poll_interval: float,
) -> tuple[int | None, bool]:
    """Wait for a child and cooperatively stop only that child when requested."""

    while True:
        returncode = process.poll()
        if returncode is not None:
            return int(returncode), False
        if _stop_requested(stop_file):
            # Give the owned injector a brief cooperative opportunity first.
            # The injector has no stop-file protocol of its own, so the
            # bounded fallback below is still limited to this worker-created
            # child and never targets Codex.
            try:
                process.wait(timeout=1)
                return None, True
            except (AttributeError, OSError, subprocess.TimeoutExpired):
                pass
            try:
                process.terminate()
            except (AttributeError, OSError, subprocess.TimeoutExpired):
                pass
            try:
                process.wait(timeout=5)
            except (AttributeError, OSError, subprocess.TimeoutExpired):
                pass
            return None, True
        _sleep(min(max(poll_interval, 0.2), 1.0), sleep_fn)


def run_worker(
    *,
    port: int | str | None = None,
    environ: Mapping[str, str] | None = None,
    root: str | os.PathLike[str] | None = None,
    injector_script: str | os.PathLike[str] | None = None,
    python_executable: str | os.PathLike[str] | None = None,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    restart_delay: float = DEFAULT_RESTART_DELAY,
    port_finder: Callable[[], int | None] | None = None,
    popen_factory: Callable[..., Any] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    mutex: NamedMutex | None = None,
    max_cycles: int | None = None,
) -> int:
    """Run the Windows worker loop.

    ``port_finder``, ``popen_factory``, ``sleep_fn``, ``mutex``, and
    ``max_cycles`` are deliberately injectable so the lifecycle can be tested
    on macOS without opening a Windows process or executing ``schtasks``.
    """

    env = dict(os.environ)
    if environ is not None:
        env.update(environ)
    resolved_port = configured_port(port, env)
    paths = adapter_paths(environ=env, root=root)
    injector = Path(injector_script) if injector_script is not None else SCRIPT_DIR / "context_token_injector.py"
    python = current_python(python_executable)
    find_port = port_finder or (lambda: find_cdp_port(resolved_port, environ=env))
    popen = popen_factory or subprocess.Popen
    owner_mutex = mutex or NamedMutex()

    if not owner_mutex.acquire():
        print("Codex quota monitor worker is already running.", file=sys.stderr, flush=True)
        return 0

    cycles = 0
    tray_process: Any | None = None
    try:
        paths.root.mkdir(parents=True, exist_ok=True)
        _write_worker_state(paths.worker_state)
        # The scheduled task owns one worker process; keep the tray attached
        # to that lifecycle so install/start results in a visible notification
        # icon. A tray failure must not stop quota collection.
        try:
            tray_kwargs: dict[str, Any] = {
                "cwd": str(paths.scripts),
                "env": tray_environment(python, env),
            }
            creation_flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if creation_flag:
                tray_kwargs["creationflags"] = creation_flag
            tray_process = popen(
                build_tray_command(tray_script=paths.scripts / "windows_tray.ps1"),
                **tray_kwargs,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"Windows tray unavailable; continuing with overlay: {exc}", file=sys.stderr, flush=True)
        while not _stop_requested(paths.stop_request):
            if max_cycles is not None and cycles >= max_cycles:
                break
            available_port = find_port()
            if available_port is None:
                print(
                    f"Waiting for Codex CDP on 127.0.0.1:{resolved_port}...",
                    file=sys.stderr,
                    flush=True,
                )
                _sleep(poll_interval, sleep_fn)
                cycles += 1
                continue

            command = build_injector_command(available_port, python, injector)
            try:
                process = popen(command, cwd=str(injector.parent), env=env)
            except OSError as exc:
                print(f"Could not start context token injector: {exc}", file=sys.stderr, flush=True)
                _sleep(restart_delay, sleep_fn)
                cycles += 1
                continue

            returncode, stopped = _wait_for_injector(
                process,
                paths.stop_request,
                sleep_fn,
                poll_interval,
            )
            if stopped or _stop_requested(paths.stop_request):
                break
            print(
                f"Context token injector disconnected (exit {returncode}); retrying.",
                file=sys.stderr,
                flush=True,
            )
            _sleep(restart_delay, sleep_fn)
            cycles += 1
    finally:
        if tray_process is not None:
            try:
                if tray_process.poll() is None:
                    tray_process.terminate()
                    tray_process.wait(timeout=5)
            except (AttributeError, OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
                pass
        _clear_worker_state(paths.worker_state)
        owner_mutex.release()
    return 0


RESET_POSITION_EXPRESSION = r"""
localStorage.removeItem('codex-context-token-inspector-position');
localStorage.removeItem('cti-layout-v2');
(()=>{const root=document.getElementById('codex-context-token-inspector-root');
if(root){root.__ctiLayout={};root.style.left='14px';root.style.top='auto';root.style.bottom='16px';}})();
true
"""

STOP_OVERLAY_EXPRESSION = r"""
window.__codexContextTokenInspectorObserver?.disconnect();
clearTimeout(window.__codexContextTokenInspectorDetailTimer);
window.cancelIdleCallback?.(window.__codexContextTokenInspectorIdleCallback || 0);
(()=>{const root=document.getElementById('codex-context-token-inspector-root');
root?.__ctiRemoveResize?.();root?.__ctiClearHint?.();})();
document.querySelectorAll('#codex-context-token-inspector-root,#codex-context-token-inspector-style,[data-context-token-chip],[data-context-token-footer],[data-context-token-badge]').forEach(n=>n.remove());
window.__codexContextTokenInspectorRuntimeVersion=null;
true
"""

SHOW_EXPRESSION = r"""
(()=>{const root=document.getElementById('codex-context-token-inspector-root');
if(root && root.getAttribute('data-collapsed')==='true')
  root.querySelector('[data-cti-toggle]')?.click();
return !!root;})();
"""


def display_action(
    action: str,
    *,
    port: int | str | None = None,
    injector_module: Any | None = None,
) -> dict[str, Any]:
    """Apply a local overlay action through the existing CDP helper."""

    if action not in {"show", "reset-position", "stop"}:
        raise ValueError(f"Unsupported display action: {action}")
    resolved_port = configured_port(port)
    client: Any | None = None
    try:
        injector = injector_module
        if injector is None:
            import context_token_injector as injector  # type: ignore[no-redef]

        target = injector.select_target(injector.devtools_targets(resolved_port))
        client = injector.CDPClient(str(target["webSocketDebuggerUrl"]))
        expression = {
            "show": SHOW_EXPRESSION,
            "reset-position": RESET_POSITION_EXPRESSION,
            "stop": STOP_OVERLAY_EXPRESSION,
        }[action]
        return {"available": True, "value": client.evaluate(expression)}
    except Exception as exc:  # CDP availability is optional for these actions.
        return {"available": False, "error": type(exc).__name__, "message": str(exc)}
    finally:
        if client is not None:
            client.close()


def _status_result(
    paths: AdapterPaths,
    task_result: Any,
    *,
    port: int,
    environ: Mapping[str, str],
) -> dict[str, Any]:
    raw = _output(task_result)
    state = _read_json(paths.worker_state)
    pid = state.get("pid") if state else None
    return {
        "task": task_state(raw) if _returncode(task_result) == 0 else "not-installed",
        "taskOutput": raw,
        "worker": {
            "pid": pid,
            "alive": _pid_alive(pid) if pid is not None else False,
        },
        "cdp": {"port": port, "available": find_cdp_port(port, environ=environ) is not None},
        "paths": paths.as_dict(),
    }


def _execute_management(
    action: str,
    plan: dict[str, Any],
    *,
    environ: Mapping[str, str],
    source_dir: str | os.PathLike[str] | None,
    root: str | os.PathLike[str] | None,
    command_runner: Callable[[Sequence[str]], Any],
) -> dict[str, Any]:
    paths = adapter_paths(environ=environ, root=root)
    commands = plan["commands"]
    if action == "install":
        copied = copy_plugin_scripts(paths.scripts, source_dir=source_dir)
        result = command_runner(commands[0])
        if _returncode(result) != 0:
            raise WindowsAdapterError(f"Could not register {TASK_NAME}: {_output(result)}")
        try:
            paths.stop_request.unlink()
        except FileNotFoundError:
            pass
        return {
            "action": action,
            "ok": True,
            "task": "registered",
            "copied": [str(path) for path in copied],
            "command": _command_result(result),
            "paths": paths.as_dict(),
        }

    if action == "start":
        if not (paths.scripts / "windows_monitor.py").is_file():
            raise WindowsAdapterError("Windows monitor is not installed; run install first")
        try:
            paths.stop_request.unlink()
        except FileNotFoundError:
            pass
        results = []
        for command in commands:
            result = command_runner(command)
            results.append(_command_result(result))
            if _returncode(result) != 0:
                raise WindowsAdapterError(f"Could not start {TASK_NAME}: {_output(result)}")
        return {"action": action, "ok": True, "commands": results, "paths": paths.as_dict()}

    if action == "stop":
        paths.root.mkdir(parents=True, exist_ok=True)
        # The marker lets a manually or scheduled worker exit without touching
        # any unrelated process.  Do not call schtasks /End here: it can end
        # the parent before its owned injector child has cleaned up.
        paths.stop_request.write_text(str(time.time()), encoding="utf-8")
        stopped = wait_for_worker_exit(paths.worker_state)
        task_result = None
        task_disabled = True
        if stopped and commands:
            task_result = command_runner(commands[0])
            task_disabled = _returncode(task_result) == 0
        overlay = display_action("stop", port=plan["port"]) if stopped else None
        return {
            "action": action,
            "ok": stopped and task_disabled,
            "cooperative": True,
            "workerStopped": stopped,
            "task": "disabled" if task_disabled else "disable-failed",
            "command": _command_result(task_result) if task_result is not None else None,
            "overlay": overlay,
            "paths": paths.as_dict(),
        }

    if action == "status":
        result = command_runner(commands[0])
        return {
            "action": action,
            "ok": True,
            "status": _status_result(
                paths,
                result,
                port=plan["port"],
                environ=environ,
            ),
        }

    if action == "doctor":
        result = command_runner(commands[0])
        status = _status_result(paths, result, port=plan["port"], environ=environ)
        app_path = find_codex_app_path(environ)
        status.update(
            {
                "action": action,
                "ok": True,
                "python": current_python(),
                "injector": (paths.scripts / "context_token_injector.py").is_file(),
                "codexApp": str(app_path) if app_path else None,
                "launchInstructions": codex_launch_instructions(plan["port"], app_path),
            }
        )
        return status

    if action in {"show", "reset-position"}:
        result = display_action(action, port=plan["port"])
        return {"action": action, "ok": True, "display": result}

    raise ValueError(f"Unsupported Windows monitor action: {action}")


def manage(
    action: str,
    *,
    environ: Mapping[str, str] | None = None,
    source_dir: str | os.PathLike[str] | None = None,
    root: str | os.PathLike[str] | None = None,
    python_executable: str | os.PathLike[str] | None = None,
    task_name: str = TASK_NAME,
    platform_name: str | None = None,
    command_runner: Callable[[Sequence[str]], Any] | None = None,
    emit: bool = True,
) -> dict[str, Any]:
    """Manage the Windows adapter or return a safe plan on other platforms.

    The optional keyword arguments are dependency-injection seams for tests
    and for the cross-platform monitor controller.  Normal callers only need
    ``manage("install")`` (and the other documented actions).
    """

    plan = build_management_plan(
        action,
        environ=environ,
        source_dir=source_dir,
        root=root,
        python_executable=python_executable,
        task_name=task_name,
    )
    effective_platform = platform_name or os.name
    if effective_platform != "nt":
        result = {
            "action": action,
            "supported": False,
            "executed": False,
            "message": "Windows adapter plan only; no Windows commands were run on this platform.",
            "plan": plan,
        }
        if emit:
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return result

    runner = command_runner or run_command
    env = dict(os.environ)
    if environ is not None:
        env.update(environ)
    result = _execute_management(
        action,
        plan,
        environ=env,
        source_dir=source_dir,
        root=root,
        command_runner=runner,
    )
    if emit:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["run", *ACTION_NAMES])
    parser.add_argument("--port", type=int, default=None, help="Loopback CDP port; defaults to CODEX_MONITOR_PORT or 9222.")
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--restart-delay", type=float, default=DEFAULT_RESTART_DELAY)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.action == "run":
        if os.name != "nt":
            print("Windows adapter worker is not runtime verified on this platform.", file=sys.stderr)
            return 2
        return run_worker(
            port=args.port,
            poll_interval=args.poll_interval,
            restart_delay=args.restart_delay,
        )

    try:
        result = manage(args.action)
    except (WindowsAdapterError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
