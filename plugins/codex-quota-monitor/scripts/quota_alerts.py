"""Optional local notifications, once per account and quota reset window."""
import hashlib
import json
from pathlib import Path
import subprocess
import time
import sys
from platform_paths import runtime_root


def eligible(quota, now=None):
    now = time.time() if now is None else now
    if quota.get('status') != 'live' or now-quota.get('updatedAt', 0) >= 120:
        return []
    account = quota.get('accountKey')
    if not account:
        return []
    return [item for item in quota.get('windows', [])
            if isinstance(item.get('remaining'), (int, float)) and item['remaining'] <= 20
            and isinstance(item.get('resetsAt'), (int, float)) and item['resetsAt'] > now]


class QuotaAlerts:
    def __init__(self, path=None, sender=None):
        self.path = path or runtime_root() / 'alerts.json'
        self.sender = sender or self._notify
        self.seen = None

    @staticmethod
    def _notify(message):
        if sys.platform == 'win32':
            # The Windows tray owns OS notification delivery.
            path=runtime_root()/'notification.json'
            path.write_text(json.dumps({'message':message,'at':time.time()}),encoding='utf-8')
            return True
        # Message is argv, never interpolated as AppleScript source.
        script = 'on run argv\ndisplay notification (item 1 of argv) with title "Codex · 用量提醒"\nend run'
        result = subprocess.run(['/usr/bin/osascript', '-e', script, message], capture_output=True, timeout=5)
        return result.returncode == 0

    def check(self, quota, enabled=False, language='zh'):
        if not enabled:
            return
        if self.seen is None:
            try:
                self.seen = json.loads(self.path.read_text())
                if not isinstance(self.seen, dict):
                    self.seen = {}
            except (OSError, ValueError):
                self.seen = {}
        for item in eligible(quota):
            raw = f"{quota['accountKey']}:{item['key']}:{item['resetsAt']}"
            key = hashlib.sha256(raw.encode()).hexdigest()
            if key in self.seen:
                continue
            label = '5 小时' if item.get('duration') == 300 else '本周' if item.get('duration') == 10080 else '当前窗口'
            message = f"{label}配额剩余 {round(item['remaining'])}%，请留意重置时间。" if language == 'zh' else f"Codex {item.get('duration', '?')}-minute window: {round(item['remaining'])}% remaining."
            try:
                if not self.sender(message):
                    continue
                self.seen[key] = item['resetsAt']
                self.seen = {k: v for k, v in self.seen.items() if isinstance(v, (int, float)) and v > time.time()}
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temp = self.path.with_suffix('.tmp')
                temp.write_text(json.dumps(self.seen))
                temp.chmod(0o600)
                temp.replace(self.path)
            except (OSError, subprocess.TimeoutExpired):
                pass
