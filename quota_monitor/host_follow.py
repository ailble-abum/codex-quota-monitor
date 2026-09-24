"""Opt-in macOS host relaunch for an explicitly configured app bundle."""
import plistlib
from pathlib import Path
import subprocess
import time


class HostFollowError(ValueError):
    pass


class HostFollower:
    """Open one known app with DevTools flags, with a short relaunch backoff."""
    def __init__(self, app_path, port, *, runner=subprocess.run, sleeper=time.sleep,
                 clock=time.monotonic, cooldown=30):
        if not isinstance(app_path, str) or '\0' in app_path:
            raise HostFollowError('invalid host app')
        path = Path(app_path)
        if not path.is_absolute() or path.suffix != '.app' or not path.is_dir():
            raise HostFollowError('invalid host app')
        if type(port) is not int or not 1 <= port <= 65535:
            raise HostFollowError('invalid host port')
        try:
            with (path / 'Contents/Info.plist').open('rb') as stream:
                info = plistlib.load(stream)
        except (OSError, ValueError, plistlib.InvalidFileException) as error:
            raise HostFollowError('invalid host app') from error
        bundle = info.get('CFBundleIdentifier')
        executable = info.get('CFBundleExecutable')
        if (not isinstance(bundle, str) or not bundle or '\0' in bundle or
                not isinstance(executable, str) or not executable or '\0' in executable):
            raise HostFollowError('invalid host app')
        if not (path / 'Contents/MacOS' / executable).is_file():
            raise HostFollowError('invalid host app')
        self.app_path, self.bundle, self.executable, self.port = path, bundle, executable, port
        self.runner, self.sleeper, self.clock, self.cooldown = runner, sleeper, clock, cooldown
        self.last_attempt = None

    def _run(self, *args):
        try:
            return self.runner(list(args), capture_output=True, text=True, check=False)
        except (OSError, TypeError):
            return None

    def _pid(self):
        result = self._run('pgrep', '-x', self.executable)
        if result is None or getattr(result, 'returncode', 1) != 0:
            return None
        for value in str(getattr(result, 'stdout', '')).split():
            if value.isdigit():
                return int(value)
        return None

    def _quit(self):
        result = self._run('osascript', '-e',
                           f'tell application id "{self.bundle}" to quit')
        return result is not None and result.returncode == 0

    def _wait_exit(self, pid):
        deadline = self.clock() + 20
        while self.clock() < deadline:
            if self._pid() != pid:
                return True
            self.sleeper(.5)
        return self._pid() != pid

    def ensure(self):
        pid = self._pid()
        if pid is None:
            return 'waiting_host'
        now = self.clock()
        if self.last_attempt is not None and now - self.last_attempt < self.cooldown:
            return 'backoff'
        self.last_attempt = now
        if not self._quit() or not self._wait_exit(pid):
            return 'quit_failed'
        args = ('open', '-a', str(self.app_path), '--args',
                '--remote-debugging-address=127.0.0.1',
                f'--remote-debugging-port={self.port}',
                f'--remote-allow-origins=http://127.0.0.1:{self.port}')
        result = self._run(*args)
        return 'launch_requested' if result is not None and result.returncode == 0 else 'launch_failed'
