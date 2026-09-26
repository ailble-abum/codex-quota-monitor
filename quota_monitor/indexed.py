"""Bounded inventory with incremental journals; directory changes invalidate it."""
import hashlib
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
                 read_budget=262144, line_limit=1048576, rescan_interval=30):
        if (any(type(x) is not int or x < 1 for x in (max_entries, max_files, read_budget))
                or read_budget < max_files or type(max_depth) is not int or not 0 <= max_depth <= 32
                or type(line_limit) is not int or line_limit < 1
                or type(rescan_interval) not in (int, float) or not math.isfinite(rescan_interval)
                or rescan_interval <= 0):
            raise ValueError('invalid directory limits')
        self.root = Path(root).absolute()
        self.max_entries, self.max_files, self.max_depth = max_entries, max_files, max_depth
        self.read_budget, self.line_limit, self.rescan_interval = read_budget, line_limit, rescan_interval
        self._dirs = None
        self._journals = {}
        self._tainted = set()
        self._next_scan = float('-inf')
        self._scan_status = 'unavailable'
        self.status, self.bytes_read = 'not_found', 0
        self.all_summaries = False

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

    def _accept_name(self, name):
        return True

    def _select_paths(self, candidates):
        if len(candidates) > self.max_files:
            raise ValueError('file limit')
        return [path for path, _modified in candidates]

    def _scan(self):
        if os.scandir not in os.supports_fd:
            raise OSError('descriptor scanning unavailable')
        candidates, directories, entries = [], {}, 0

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
                    elif stat.S_ISREG(info.st_mode) and entry.name.endswith('.jsonl') and self._accept_name(entry.name):
                        candidates.append((path, info.st_mtime_ns))
            if signature(os.fstat(descriptor)) != before:
                raise ValueError('directory changed')

        descriptor = open_in_root(self.root, '.', directory=True)
        try:
            visit(descriptor, Path('.'), 0)
        finally:
            os.close(descriptor)
        paths = self._select_paths(candidates)
        old = self._journals
        self._journals = {path: old[path] if path in old else SessionJournal(
            path, root=self.root, line_limit=self.line_limit)
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

        readings, selected_readings = [], []
        selected_paths = ([path for path in self._journals
                           if self.all_summaries and path.name.endswith('-' + key + '.jsonl')]
                          if self.all_summaries else [])
        background_count = len(self._journals) - len(selected_paths)
        selected_quota = 0
        if selected_paths:
            selected_quota = min(2 * 1024 * 1024,
                                 max(1, (self.read_budget - background_count) // len(selected_paths)))
        remaining = self.read_budget - selected_quota * len(selected_paths)
        background_quota = (min(16384, max(1, remaining // background_count))
                            if background_count else 0)
        quota = self.read_budget // max(1, len(self._journals))
        for path, journal in self._journals.items():
            selected_name = path in selected_paths
            if selected_name:
                # Keep the active task responsive even when sidebar inventory
                # contains many older logs; the rollout adapter allows a
                # bounded compacted line up to its 2 MiB reader limit.
                journal.reader.read_budget = selected_quota
            elif self.all_summaries:
                journal.reader.read_budget = background_quota
            else:
                journal.reader.read_budget = min(quota, 16384)
            reading = journal.poll()
            self.bytes_read += reading['bytes_read']
            if reading['reset']:
                self._tainted.discard(path)
            if reading['invalid_lines']:
                self._tainted.add(path)
            readings.append(reading)
            if selected_name:
                selected_readings.append(reading)
        if not self._current():
            self.status = 'index_wait'
        elif self.all_summaries:
            # A background task may have a large or partial log. Keep the
            # selected task responsive and omit only non-ready sidebar rows.
            matches = [r for r in selected_readings if r['thread_id'] == key and
                       r.get('status') == 'ok' and r.get('identity_status') == 'verified']
            selected_loading = any(r.get('status') == 'ok' and (r.get('more') or r.get('pending'))
                                   for r in selected_readings)
            self.status = ('ambiguous' if len(matches) > 1 else
                           'loading' if selected_loading else 'ok' if matches else 'not_found')
            if self.status == 'ok':
                verified = {}
                duplicate = set()
                for reading in readings:
                    thread_id = reading.get('thread_id')
                    if (reading.get('status') != 'ok' or
                            reading.get('identity_status') != 'verified' or
                            not isinstance(thread_id, str)):
                        continue
                    if thread_id in verified:
                        duplicate.add(thread_id)
                    else:
                        verified[thread_id] = reading
                for thread_id in duplicate:
                    verified.pop(thread_id, None)
                return panel_payload(verified, key, allow_partial=True)
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
                if not self.all_summaries:
                    return panel_payload({key: matches[0]}, key)
                verified = {}
                duplicate = set()
                for reading in readings:
                    thread_id = reading.get('thread_id')
                    if (reading.get('identity_status') != 'verified' or
                            not isinstance(thread_id, str)):
                        continue
                    if thread_id in verified:
                        duplicate.add(thread_id)
                    else:
                        verified[thread_id] = reading
                for thread_id in duplicate:
                    verified.pop(thread_id, None)
                return panel_payload(verified, key)
        return empty


class NamedDirectorySource(DirectorySource):
    """Opt-in Codex rollout filename selection; contents must still verify identity."""
    def __init__(self, root):
        # Codex compacted records can contain bounded replacement history just
        # above the generic 1 MiB JSONL line limit. Keep the larger allowance
        # scoped to the explicit rollout adapter; ordinary journals retain the
        # stricter default.
        super().__init__(root, read_budget=4 * 1024 * 1024, line_limit=2 * 1024 * 1024)
        self._selected_key = None
        self._selected_tails = {}
        self.all_summaries = True

    def _accept_name(self, name):
        if not name.startswith('rollout-') or not name.endswith('.jsonl'):
            return False
        suffix = name[:-len('.jsonl')].rsplit('-', 1)[-1]
        # Real rollout names end in a UUID-like task key. Keep the synthetic
        # short keys used by offline tests, while ignoring numeric noise files.
        return len(suffix) >= 3 and not suffix.isdigit()

    def _select_paths(self, candidates):
        suffix = '-' + self._selected_key + '.jsonl'
        selected = [(path, modified) for path, modified in candidates if path.name.endswith(suffix)]
        if len(selected) > self.max_files:
            raise ValueError('file limit')
        selected_paths = {path for path, _modified in selected}
        recent = sorted((item for item in candidates if item[0] not in selected_paths),
                        key=lambda item: (item[1], str(item[0])), reverse=True)
        return [path for path, _modified in selected + recent[:self.max_files - len(selected)]]

    def _tail_fingerprint(self, path, offset):
        try:
            descriptor = open_in_root(self.root, path)
            try:
                info = os.fstat(descriptor)
                if info.st_size < offset:
                    return None
                size = min(64, offset)
                os.lseek(descriptor, offset - size, os.SEEK_SET)
                return ((info.st_dev, info.st_ino), offset,
                        hashlib.sha256(os.read(descriptor, size)).digest())
            finally:
                os.close(descriptor)
        except OSError:
            return None

    def _drop_changed_selected(self, key):
        suffix = '-' + key + '.jsonl'
        for path, journal in list(self._journals.items()):
            if not path.name.endswith(suffix):
                continue
            expected = self._selected_tails.get(path)
            actual = self._tail_fingerprint(path, journal.reader._offset)
            if expected is None or actual != expected:
                self._journals.pop(path, None)
                self._tainted.discard(path)
                self._selected_tails.pop(path, None)

    def _remember_selected(self, key):
        self._selected_tails = {path: value for path, value in self._selected_tails.items()
                                if path in self._journals}
        suffix = '-' + key + '.jsonl'
        for path, journal in self._journals.items():
            if path.name.endswith(suffix):
                fingerprint = self._tail_fingerprint(path, journal.reader._offset)
                if fingerprint is not None:
                    self._selected_tails[path] = fingerprint

    def read(self, key):
        if thread_key(key) != key or key is None:
            self.status = 'not_found'
            return panel_payload({}, None)
        if key != self._selected_key:
            self._drop_changed_selected(key)
            self._selected_key = key
            self._dirs = None
            self._next_scan = float('-inf')
        result = super().read(key)
        self._remember_selected(key)
        return result
