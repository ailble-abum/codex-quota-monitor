"""Bounded, read-only polling of append-only UTF-8 JSON object journals.

Records are internal input, not a safe-to-publish snapshot. Consumers must
project allowed fields before displaying, logging, or persisting them.
"""
import json
import math
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class ReadBatch:
    records: List[Dict[str, Any]] = field(default_factory=list, repr=False)
    bytes_read: int = 0
    invalid_lines: int = 0
    reset: bool = False
    more: bool = False
    status: str = 'ok'


def reject_constant(value):
    raise ValueError('nonfinite JSON number')


def finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('overflowing JSON number')
    return number


class JournalReader:
    def __init__(self, path, *, read_budget=262144, line_limit=1048576):
        if read_budget <= 0 or line_limit <= 0:
            raise ValueError('limits must be positive')
        self.path = Path(path)
        self.read_budget = read_budget
        self.line_limit = line_limit
        self._identity = None
        self._offset = 0
        self._pending = b''
        self._discarding = False

    def poll(self):
        result = ReadBatch()
        try:
            descriptor = os.open(self.path, os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0))
            with os.fdopen(descriptor, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode):
                    result.status = 'unavailable'
                    return result
                identity = (info.st_dev, info.st_ino)
                changed = self._identity is not None and (
                    identity != self._identity or info.st_size < self._offset)
                offset = 0 if changed else self._offset
                stream.seek(offset)
                data = stream.read(min(self.read_budget, max(0, info.st_size - offset)))
        except OSError:
            result.status = 'unavailable'
            return result

        # Commit the cursor only after a successful read. A temporary open/read
        # failure must not discard a pending line or replay old records.
        if changed:
            self._pending = b''
            self._discarding = False
        self._identity = identity
        self._offset = offset + len(data)
        result.reset = changed
        result.bytes_read = len(data)
        result.more = self._offset < info.st_size
        fragments = data.split(b'\n')
        for index, fragment in enumerate(fragments):
            complete = index < len(fragments) - 1
            if not self._discarding:
                if len(self._pending) + len(fragment) > self.line_limit:
                    self._pending = b''
                    self._discarding = True
                    result.invalid_lines += 1
                else:
                    self._pending += fragment
            if not complete:
                continue
            if not self._discarding and self._pending.strip():
                try:
                    record = json.loads(self._pending.decode('utf-8'),
                                        parse_constant=reject_constant,
                                        parse_float=finite_float)
                    if not isinstance(record, dict):
                        raise ValueError('expected an object')
                except (ValueError, UnicodeError, RecursionError):
                    result.invalid_lines += 1
                else:
                    result.records.append(record)
            self._pending = b''
            self._discarding = False
        return result
