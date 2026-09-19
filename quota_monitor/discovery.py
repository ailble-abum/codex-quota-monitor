"""Bounded lookup in an explicitly selected journal directory."""
import os
from pathlib import Path

from .compat import thread_key
from .journal import SessionJournal


def discover(root, thread_id, *, max_entries=4096, max_bytes=16777216, max_depth=8):
    key = thread_key(thread_id)
    if (key is None or type(max_entries) is not int or max_entries < 1
            or type(max_bytes) is not int or max_bytes < 1
            or type(max_depth) is not int or not 0 <= max_depth <= 32):
        raise ValueError('invalid task or scan limits')
    root = Path(root)
    result = {'status': 'not_found', 'reading': None, 'entries': 0,
              'files': 0, 'bytes_read': 0, 'invalid_lines': 0}
    matches = 0

    def visit(directory, depth):
        nonlocal matches
        with os.scandir(directory) as entries:
            for entry in entries:
                if result['entries'] >= max_entries:
                    return False
                result['entries'] += 1
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if depth >= max_depth or not visit(entry.path, depth + 1):
                        return False
                    continue
                if not entry.name.endswith('.jsonl') or not entry.is_file(follow_symlinks=False):
                    continue
                result['files'] += 1
                journal = SessionJournal(entry.path)
                while True:
                    remaining = max_bytes - result['bytes_read']
                    if remaining <= 0:
                        return False
                    journal.reader.read_budget = min(262144, remaining)
                    reading = journal.poll()
                    result['bytes_read'] += reading['bytes_read']
                    result['invalid_lines'] += reading['invalid_lines']
                    if reading['status'] != 'ok' or reading['reset'] or reading['invalid_lines']:
                        return False
                    if not reading['more']:
                        break
                    if not reading['bytes_read']:
                        return False
                if reading['pending'] or reading['identity_status'] != 'verified':
                    return False
                if reading['thread_id'] == key:
                    matches += 1
                    result['reading'] = reading if matches == 1 else None
        return True

    try:
        if root.is_symlink() or not root.is_dir():
            result['status'] = 'unavailable'
            return result
        complete = visit(root, 0)
    except OSError:
        result['status'] = 'incomplete' if result['entries'] else 'unavailable'
        result['reading'] = None
        return result
    if not complete:
        result['status'] = 'incomplete'
        result['reading'] = None
    else:
        result['status'] = 'ambiguous' if matches > 1 else 'ok' if matches else 'not_found'
    return result
