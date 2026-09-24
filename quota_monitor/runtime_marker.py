"""Small local runtime marker for doctor; contains no session or account data."""
import json
import os
from pathlib import Path
import re
import tempfile
import time


STATUS = re.compile(r'^[a-z][a-z0-9_]{0,63}$')


class StatusStore:
    def __init__(self, root, *, clock=time.time):
        self.path = Path(root).absolute() / 'status.json'
        self.clock = clock
        self.last_status, self.last_write = None, float('-inf')

    def write(self, status):
        if not isinstance(status, str) or not STATUS.fullmatch(status):
            raise ValueError('invalid runtime status')
        now = self.clock()
        if status == self.last_status and now - self.last_write < 30:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix='.status-', dir=str(self.path.parent))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump({'status': status, 'updatedAt': now}, stream)
                stream.write('\n')
            os.chmod(temp, 0o600)
            os.replace(temp, self.path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        self.last_status, self.last_write = status, now

    def read(self, *, max_age=120):
        try:
            with self.path.open('rb') as stream:
                raw = stream.read(513)
            if len(raw) > 512:
                return 'invalid'
            value = json.loads(raw)
        except (OSError, ValueError, RecursionError):
            return 'missing'
        if not isinstance(value, dict) or not isinstance(value.get('status'), str) or not STATUS.fullmatch(value['status']):
            return 'invalid'
        stamp = value.get('updatedAt')
        now = self.clock()
        if type(stamp) not in (int, float) or not 0 <= now - stamp <= max_age:
            return 'stale'
        return value['status']
