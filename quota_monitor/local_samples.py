"""Opt-in local numeric samples for the V2 runtime."""

import json
import math
import os
import tempfile
import time
from pathlib import Path


def _number(value, low=0, high=8.64e12):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def _finite_text(value, limit=128):
    return value[:limit] if isinstance(value, str) and value and len(value) <= limit else None


def _windows(value):
    result = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict) or not _finite_text(item.get('key'), 32):
            continue
        remaining = item.get('remaining')
        if not _number(remaining, high=100):
            continue
        result.append({'key': item['key'], 'remaining': remaining})
    return result[:4]


class LocalSampleStore:
    """Persist bounded, privacy-minimal samples when explicitly configured."""

    def __init__(self, root, *, retention=7 * 86400, max_rows=10080, clock=time.time):
        if not isinstance(root, (str, Path)) or not str(root) or '\0' in str(root):
            raise ValueError('invalid local sample root')
        if type(retention) is not int or retention < 60 or type(max_rows) is not int or max_rows < 1:
            raise ValueError('invalid sample limits')
        self.root = Path(root).absolute()
        self.retention, self.max_rows, self.clock = retention, max_rows, clock
        self.last = 0.0
        self.rows = []
        self._load()

    def _load(self):
        try:
            value = json.loads((self.root / 'history.json').read_text(encoding='utf-8'))
            self.rows = value if isinstance(value, list) else []
        except (OSError, ValueError, RecursionError):
            self.rows = []
        self.rows = self._clean(self.rows, self.clock())

    def _clean(self, rows, now):
        result = []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict) or not _number(row.get('at'), 0) or now - row['at'] > self.retention:
                continue
            result.append(row)
        return result[-self.max_rows:]

    def record(self, quota, context, health, model=None):
        now = self.clock()
        if not _number(now, 0) or now - self.last < 30:
            return self.summary()
        self.last = now
        context = context if isinstance(context, dict) else {}
        row = {
            'at': now,
            'windows': _windows(quota.get('windows') if isinstance(quota, dict) else None),
            'context': {
                'latest_context_percent': context.get('latest_context_percent')
                if _number(context.get('latest_context_percent'), high=100) else None,
                'latest_turn_input_tokens': context.get('latest_turn_input_tokens')
                if _number(context.get('latest_turn_input_tokens')) else None,
                'latest_turn_cached_input_tokens': context.get('latest_turn_cached_input_tokens')
                if _number(context.get('latest_turn_cached_input_tokens')) else None,
            },
            'health': {'count': health.get('count') if isinstance(health, dict) and
                       type(health.get('count')) is int and health.get('count') >= 0 else 0},
        }
        name = _finite_text(model)
        if name:
            row['model'] = name
        self.rows = self._clean(self.rows + [row], now)
        self._write()
        return self.summary()

    def _write(self):
        self.root.mkdir(parents=True, exist_ok=True)
        fd, raw = tempfile.mkstemp(prefix='.samples-', dir=str(self.root))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(self.rows, stream, ensure_ascii=False, separators=(',', ':'))
                stream.write('\n')
            os.chmod(raw, 0o600)
            os.replace(raw, self.root / 'history.json')
        finally:
            try:
                os.unlink(raw)
            except FileNotFoundError:
                pass

    def summary(self):
        rows = self.rows
        times = [row['at'] for row in rows if _number(row.get('at'), 0)]
        remaining = [window['remaining'] for row in rows
                     for window in (row.get('windows') if isinstance(row.get('windows'), list) else [])
                     if isinstance(window, dict) and _number(window.get('remaining'), high=100)]
        contexts = []
        for row in rows:
            context = row.get('context') if isinstance(row.get('context'), dict) else {}
            value = context.get('latest_context_percent')
            if _number(value, high=100):
                contexts.append(value)
        cached = []
        for row in rows:
            context = row.get('context') if isinstance(row.get('context'), dict) else {}
            total, hit = context.get('latest_turn_input_tokens'), context.get('latest_turn_cached_input_tokens')
            if _number(total, low=1) and _number(hit, low=0) and hit <= total:
                cached.append(100 * hit / total)
        by_model = {}
        for row in rows:
            name = row.get('model')
            if name:
                by_model[name] = by_model.get(name, 0) + 1
        return {
            'samples': len(rows),
            'spanSeconds': max(times) - min(times) if len(times) > 1 else 0,
            'minRemaining': min(remaining) if remaining else None,
            'peakContext': max(contexts) if contexts else None,
            'averageCachedShare': sum(cached) / len(cached) if cached else None,
            'models': sorted(by_model, key=lambda key: (-by_model[key], key))[:6],
        }
