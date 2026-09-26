"""Bounded inventory with incremental journals; directory changes invalidate it."""
import hashlib
import math
import os
from pathlib import Path
import stat
import time

from .compat import panel_payload, panel_summary, thread_key
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

    def _read_progress(self, paths):
        read_bytes, total_bytes = 0, 0
        try:
            for path in paths:
                journal = self._journals[path]
                descriptor = open_in_root(self.root, path)
                try:
                    info = os.fstat(descriptor)
                finally:
                    os.close(descriptor)
                if (not stat.S_ISREG(info.st_mode) or
                        (info.st_dev, info.st_ino) != journal.reader._identity or
                        info.st_size < journal.reader._offset):
                    return None
                read_bytes += journal.reader._offset
                total_bytes += info.st_size
        except OSError:
            return None
        return read_bytes, total_bytes

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
        priority_key = getattr(self, '_priority_key', None) if self.all_summaries else None

        def publish(payload, status=None):
            if priority_key is not None:
                payload['sidebarStatus'] = {
                    'threadId': priority_key,
                    'status': status or 'unavailable',
                }
            return payload

        self.bytes_read = 0
        if key is None:
            self.status = 'not_found'
            return publish(empty)
        inventory_wait = False
        if not self._current():
            now = time.monotonic()
            if now < self._next_scan:
                self.status = 'index_wait' if self._dirs is not None else self._scan_status
                # A changed inventory does not make already-open, explicitly
                # named journals unsafe. Continue polling those journals while
                # the bounded rescan is cooling down, but report that a missing
                # hover target may still be waiting for the next inventory.
                inventory_wait = self._dirs is not None
                if not inventory_wait:
                    return publish(empty)
            else:
                self._next_scan = now + self.rescan_interval
                try:
                    self._scan()
                    self._scan_status = 'ok'
                except (OSError, ValueError) as error:
                    self._dirs, self._journals, self._tainted = None, {}, set()
                    self._scan_status = 'unavailable' if isinstance(error, OSError) else 'incomplete'
                    self.status = self._scan_status
                    return publish(empty)

        readings, selected_readings, path_readings = [], [], []
        selected_paths = ([path for path in self._journals
                           if self.all_summaries and path.name.endswith('-' + key + '.jsonl')]
                          if self.all_summaries else [])
        priority_paths = ([path for path in self._journals
                           if priority_key is not None and
                           path.name.endswith('-' + priority_key + '.jsonl')]
                          if self.all_summaries else [])
        priority_only = [path for path in priority_paths if path not in selected_paths]
        background_paths = [path for path in self._journals
                            if path not in selected_paths and path not in priority_only]
        ordered_paths = (selected_paths + priority_only + background_paths
                         if self.all_summaries else list(self._journals))
        remaining_budget = self.read_budget
        active_budget = min(2 * 1024 * 1024,
                            max(0, remaining_budget - len(priority_only) - len(background_paths)))
        group_remaining = active_budget
        active_left = len(selected_paths)
        priority_remaining = None
        priority_left = len(priority_only)
        quota = self.read_budget // max(1, len(self._journals))
        for index, path in enumerate(ordered_paths):
            journal = self._journals[path]
            selected_name = path in selected_paths
            priority_name = path in priority_only
            reserve = len(ordered_paths) - index - 1
            available = max(1, remaining_budget - reserve)
            if not self.all_summaries:
                allocation = min(quota, 16384)
            elif selected_name:
                allocation = max(1, min(available,
                                        group_remaining // max(1, active_left)))
            elif priority_name:
                if priority_remaining is None:
                    priority_remaining = max(1, remaining_budget - len(background_paths))
                allocation = max(1, min(available,
                                        priority_remaining // max(1, priority_left)))
            else:
                # Drain the remaining budget through recent background files.
                # Completed files consume zero, so the next file immediately
                # inherits their unused allowance instead of waiting at 16 KiB.
                allocation = available
            journal.reader.read_budget = allocation
            reading = journal.poll()
            self.bytes_read += reading['bytes_read']
            remaining_budget -= reading['bytes_read']
            if selected_name:
                group_remaining = max(0, group_remaining - reading['bytes_read'])
                active_left -= 1
            elif priority_name:
                priority_remaining = max(0, priority_remaining - reading['bytes_read'])
                priority_left -= 1
            if reading['reset']:
                self._tainted.discard(path)
            if reading['invalid_lines']:
                self._tainted.add(path)
            readings.append(reading)
            path_readings.append((path, reading))
            if selected_name:
                selected_readings.append(reading)
        sidebar_status = None
        sidebar_progress = None
        if priority_key is not None:
            priority_readings = [reading for path, reading in path_readings
                                 if path in priority_paths]
            if not priority_paths:
                sidebar_status = 'index_wait' if inventory_wait else 'not_found'
            elif any(reading.get('status') != 'ok' for reading in priority_readings):
                sidebar_status = 'unavailable'
            elif any(reading.get('more') or reading.get('pending')
                     for reading in priority_readings):
                sidebar_status = 'loading'
                if any(reading.get('more') for reading in priority_readings):
                    sidebar_progress = self._read_progress(priority_paths)
            else:
                matches = [reading for reading in priority_readings
                           if reading.get('thread_id') == priority_key and
                           reading.get('identity_status') == 'verified']
                sidebar_status = ('ambiguous' if len(matches) > 1 else
                                  'ready' if matches else 'not_found')
        if not self._current():
            inventory_wait = True
            self.status = 'index_wait'
        if self.all_summaries and inventory_wait:
            # Directory changes can introduce a second file claiming the same
            # task identity. Advancing known journal cursors is safe, but no
            # summary is publishable until a fresh inventory proves uniqueness.
            return publish(empty, 'index_wait')
        if self.all_summaries:
            # A background task may have a large or partial log. Keep the
            # selected task responsive and omit only non-ready sidebar rows.
            matches = [r for r in selected_readings if r['thread_id'] == key and
                       r.get('status') == 'ok' and r.get('identity_status') == 'verified']
            selected_loading = any(r.get('status') == 'ok' and (r.get('more') or r.get('pending'))
                                   for r in selected_readings)
            selected_status = ('ambiguous' if len(matches) > 1 else
                               'loading' if selected_loading else 'ok' if matches else 'not_found')
            self.status = selected_status
            verified = {}
            duplicate = set()
            for path, reading in path_readings:
                candidate = reading.get('thread_id')
                if (reading.get('status') != 'ok' or
                        reading.get('identity_status') != 'verified' or
                        not isinstance(candidate, str) or
                        not path.name.endswith('-' + candidate + '.jsonl')):
                    continue
                if candidate in verified:
                    duplicate.add(candidate)
                else:
                    verified[candidate] = reading
            for candidate in duplicate:
                verified.pop(candidate, None)

            # Active details and sidebar summaries have independent readiness.
            # A very large active journal can take minutes to drain, while an
            # explicitly hovered task is already complete. Publish that
            # identity-verified complete sidebar summary without claiming the
            # active task itself is selected or ready.
            payload = (panel_payload(verified, key, allow_partial=True)
                       if selected_status == 'ok' else panel_payload({}, key))
            if payload['selectedThreadId'] is None and priority_key is not None:
                payload['summaries'] = [summary for candidate, reading in verified.items()
                                        if (summary := panel_summary(candidate, reading)) is not None]
            if sidebar_progress is not None:
                payload['sidebarStatus'] = {
                    'threadId': priority_key, 'status': sidebar_status,
                    'readBytes': sidebar_progress[0], 'totalBytes': sidebar_progress[1],
                }
                return payload
            return publish(payload, sidebar_status)
        elif inventory_wait:
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
                if not self.all_summaries:
                    return publish(panel_payload({key: matches[0]}, key), sidebar_status)
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
                return publish(panel_payload(verified, key), sidebar_status)
        return publish(empty, sidebar_status)


class NamedDirectorySource(DirectorySource):
    """Opt-in Codex rollout filename selection; contents must still verify identity."""
    def __init__(self, root):
        # Codex compacted records can contain bounded replacement history just
        # above the generic 1 MiB JSONL line limit. Keep the larger allowance
        # scoped to the explicit rollout adapter; ordinary journals retain the
        # stricter default.
        super().__init__(root, read_budget=4 * 1024 * 1024, line_limit=2 * 1024 * 1024)
        self._selected_key = None
        self._priority_key = None
        self._selected_tails = {}
        self.all_summaries = True

    def _accept_name(self, name):
        if not name.startswith('rollout-') or not name.endswith('.jsonl'):
            return False
        stem = name[:-len('.jsonl')]
        suffix = stem.rsplit('-', 1)[-1]
        uuid_parts = stem.split('-')[-5:]
        uuid_suffix = (len(uuid_parts) == 5 and
                       [len(part) for part in uuid_parts] == [8, 4, 4, 4, 12] and
                       all(part and all(char in '0123456789abcdefABCDEF' for char in part)
                           for part in uuid_parts))
        # Real rollout names end in a UUID-like task key. Keep the synthetic
        # short keys used by offline tests, while ignoring numeric noise files.
        return uuid_suffix or (len(suffix) >= 3 and not suffix.isdigit())

    def _select_paths(self, candidates):
        keys = [key for key in (self._selected_key, self._priority_key) if key is not None]
        selected = [(path, modified) for path, modified in candidates
                    if any(path.name.endswith('-' + key + '.jsonl') for key in keys)]
        if len(selected) > self.max_files:
            raise ValueError('file limit')
        selected_paths = {path for path, _modified in selected}
        recent = sorted((item for item in candidates if item[0] not in selected_paths),
                        key=lambda item: (item[1], str(item[0])), reverse=True)
        return [path for path, _modified in selected + recent[:self.max_files - len(selected)]]

    def _file_fingerprint(self, path, offset):
        try:
            descriptor = open_in_root(self.root, path)
            try:
                info = os.fstat(descriptor)
                if info.st_size < offset:
                    return None
                size = min(64, offset)
                os.lseek(descriptor, 0, os.SEEK_SET)
                head = hashlib.sha256(os.read(descriptor, size)).digest()
                os.lseek(descriptor, offset - size, os.SEEK_SET)
                tail = hashlib.sha256(os.read(descriptor, size)).digest()
                return ((info.st_dev, info.st_ino), offset, info.st_size,
                        info.st_mtime_ns, info.st_ctime_ns, head, tail)
            finally:
                os.close(descriptor)
        except OSError:
            return None

    def _matches_fingerprint(self, path, expected):
        actual = self._file_fingerprint(path, expected[1])
        if actual is None or actual[0] != expected[0] or actual[2] < expected[2]:
            return False
        if actual[5:] != expected[5:]:
            return False
        # Growth may be an append and is verified by the saved prefix windows.
        # Same-size metadata changes are conservatively treated as a rewrite.
        return actual[2] > expected[2] or actual[3:5] == expected[3:5]

    def _drop_changed_selected(self, key):
        suffix = '-' + key + '.jsonl'
        for path, journal in list(self._journals.items()):
            if not path.name.endswith(suffix):
                continue
            expected = self._selected_tails.get(path)
            if expected is None or not self._matches_fingerprint(path, expected):
                self._journals.pop(path, None)
                self._tainted.discard(path)
                self._selected_tails.pop(path, None)

    def _remember_journals(self):
        self._selected_tails = {path: value for path, value in self._selected_tails.items()
                                if path in self._journals}
        for path, journal in self._journals.items():
            fingerprint = self._file_fingerprint(path, journal.reader._offset)
            if fingerprint is not None:
                self._selected_tails[path] = fingerprint

    def prioritize(self, key):
        if key is not None and thread_key(key) != key:
            raise ValueError('invalid task key')
        if key == self._priority_key:
            return
        if key is not None:
            self._drop_changed_selected(key)
        self._priority_key = key
        self._dirs = None
        self._next_scan = float('-inf')

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
        self._remember_journals()
        return result
