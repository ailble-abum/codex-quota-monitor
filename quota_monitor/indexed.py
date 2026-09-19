"""Bounded inventory with incremental journals; directory changes invalidate it."""
import math
import os
from pathlib import Path
import stat
import time

from .compat import panel_payload, thread_key
from .journal import SessionJournal
from .reader import open_in_root


def signature(info):
    return info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns


class DirectorySource:
    def __init__(self, root, *, max_entries=4096, max_files=128, max_depth=8,
                 read_budget=262144, rescan_interval=30):
        if (any(type(x) is not int or x < 1 for x in (max_entries, max_files, read_budget))
                or read_budget < max_files or type(max_depth) is not int or not 0 <= max_depth <= 32
                or type(rescan_interval) not in (int, float) or not math.isfinite(rescan_interval)
                or rescan_interval <= 0):
            raise ValueError('invalid directory limits')
        self.root = Path(root).absolute()
        self.max_entries, self.max_files, self.max_depth = max_entries, max_files, max_depth
        self.read_budget, self.rescan_interval = read_budget, rescan_interval
        self._dirs = None
        self._journals = {}
        self._tainted = set()
        self._next_scan = float('-inf')
        self._scan_status = 'unavailable'
        self.status, self.bytes_read = 'not_found', 0

    def _current(self):
        if self._dirs is None:
            return False
        try:
            for path, expected in self._dirs.items():
                descriptor = open_in_root(self.root, path, directory=True)
                try:
                    if signature(os.fstat(descriptor)) != expected:
                        return False
                finally:
                    os.close(descriptor)
        except OSError:
            return False
        return True

    def _scan(self):
        if os.scandir not in os.supports_fd:
            raise OSError('descriptor scanning unavailable')
        paths, directories, entries = [], {}, 0

        def visit(descriptor, relative, depth):
            nonlocal entries
            before = signature(os.fstat(descriptor))
            directories[relative] = before
            with os.scandir(descriptor) as children:
                for entry in children:
                    entries += 1
                    if entries > self.max_entries:
                        raise ValueError('entry limit')
                    info = entry.stat(follow_symlinks=False)
                    path = relative / entry.name
                    if stat.S_ISDIR(info.st_mode):
                        if depth >= self.max_depth:
                            raise ValueError('depth limit')
                        child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                        dir_fd=descriptor)
                        try:
                            visit(child, path, depth + 1)
                        finally:
                            os.close(child)
                    elif stat.S_ISREG(info.st_mode) and entry.name.endswith('.jsonl'):
                        paths.append(path)
                        if len(paths) > self.max_files:
                            raise ValueError('file limit')
            if signature(os.fstat(descriptor)) != before:
                raise ValueError('directory changed')

        descriptor = open_in_root(self.root, '.', directory=True)
        try:
            visit(descriptor, Path('.'), 0)
        finally:
            os.close(descriptor)
        old = self._journals
        self._journals = {path: old[path] if path in old else SessionJournal(path, root=self.root)
                          for path in paths}
        self._tainted.intersection_update(paths)
        self._dirs = directories

    def read(self, thread_id):
        key = thread_key(thread_id)
        empty = panel_payload({}, key)
        self.bytes_read = 0
        if key is None:
            self.status = 'not_found'
            return empty
        if not self._current():
            now = time.monotonic()
            if now < self._next_scan:
                self.status = 'index_wait' if self._dirs is not None else self._scan_status
                return empty
            self._next_scan = now + self.rescan_interval
            try:
                self._scan()
                self._scan_status = 'ok'
            except (OSError, ValueError) as error:
                self._dirs, self._journals, self._tainted = None, {}, set()
                self._scan_status = 'unavailable' if isinstance(error, OSError) else 'incomplete'
                self.status = self._scan_status
                return empty

        readings = []
        quota = self.read_budget // max(1, len(self._journals))
        for path, journal in self._journals.items():
            journal.reader.read_budget = quota
            reading = journal.poll()
            self.bytes_read += reading['bytes_read']
            if reading['reset']:
                self._tainted.discard(path)
            if reading['invalid_lines']:
                self._tainted.add(path)
            readings.append(reading)
        if not self._current():
            self.status = 'index_wait'
        elif any(r['status'] != 'ok' for r in readings):
            self.status = 'unavailable'
        elif self._tainted:
            self.status = 'incomplete'
        elif any(r['more'] for r in readings):
            self.status = 'loading'
        elif any(r['pending'] or r['identity_status'] != 'verified' for r in readings):
            self.status = 'incomplete'
        else:
            matches = [r for r in readings if r['thread_id'] == key]
            self.status = 'ambiguous' if len(matches) > 1 else 'ok' if matches else 'not_found'
            if self.status == 'ok':
                return panel_payload({key: matches[0]}, key)
        return empty
