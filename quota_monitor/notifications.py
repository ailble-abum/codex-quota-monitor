"""Opt-in, account-scoped local quota notifications for macOS."""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _send(message):
    if sys.platform != 'darwin':
        return False
    script = ('on run argv\n'
              'display notification (item 1 of argv) with title "Codex · 用量提醒"\n'
              'end run')
    result = subprocess.run(['/usr/bin/osascript', '-e', script, message],
                            capture_output=True, timeout=5, check=False)
    return result.returncode == 0


class QuotaNotifier:
    def __init__(self, root, *, sender=_send, clock=time.time):
        self.path = Path(root).absolute() / 'notifications.json'
        self.sender, self.clock = sender, clock
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            self.seen = data if isinstance(data, dict) else {}
        except (OSError, ValueError, RecursionError):
            self.seen = {}

    def notify(self, quota):
        now = self.clock()
        if (not isinstance(quota, dict) or quota.get('status') != 'live' or
                not _number(quota.get('updatedAt')) or not 0 <= now - quota['updatedAt'] < 120 or
                not isinstance(quota.get('accountKey'), str) or len(quota['accountKey']) != 64):
            return 0
        sent = 0
        for window in quota.get('windows', []) if isinstance(quota.get('windows'), list) else []:
            if (not isinstance(window, dict) or window.get('key') not in ('primary', 'secondary') or
                    not _number(window.get('remaining')) or not 0 <= window['remaining'] <= 20 or
                    not _number(window.get('resetsAt')) or window['resetsAt'] <= now):
                continue
            identity = json.dumps([quota['accountKey'], window['key'], window['resetsAt']])
            key = hashlib.sha256(identity.encode()).hexdigest()
            if key in self.seen:
                continue
            message = '{}配额剩余 {}%，请留意重置时间。'.format(
                '5 小时' if window.get('duration') == 300 else '本周' if window.get('duration') == 10080
                else '当前窗口', round(window['remaining']))
            try:
                if not self.sender(message):
                    continue
                self.seen[key] = window['resetsAt']
                self.seen = {key: expiry for key, expiry in self.seen.items()
                             if _number(expiry) and expiry > now}
                self.path.parent.mkdir(parents=True, exist_ok=True)
                fd, temp = tempfile.mkstemp(prefix='.notifications-', dir=str(self.path.parent))
                try:
                    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                        json.dump(self.seen, stream)
                    os.chmod(temp, 0o600)
                    os.replace(temp, self.path)
                finally:
                    if os.path.exists(temp):
                        os.unlink(temp)
                sent += 1
            except (OSError, subprocess.TimeoutExpired):
                continue
        return sent
