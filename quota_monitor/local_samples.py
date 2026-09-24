"""Opt-in local numeric samples for the V2 runtime."""

import json
import math
import os
import tempfile
import time
from datetime import datetime, timezone
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


def _account_key(quota):
    value = quota.get('accountKey') if isinstance(quota, dict) else None
    return value if isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value) else None


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
            return self.summary(_account_key(quota))
        self.last = now
        context = context if isinstance(context, dict) else {}
        row = {
            'at': now,
            'accountKey': _account_key(quota),
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
        return self.summary(_account_key(quota))

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

    def summary(self, account_key=None):
        rows = [row for row in self.rows if row.get('accountKey') == account_key]
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
            name = _finite_text(row.get('model'))
            if name:
                by_model[name] = by_model.get(name, 0) + 1
        today = int(self.clock() // 86400)
        days = []
        for day in range(today - 6, today + 1):
            matching = [row for row in rows if int(row['at'] // 86400) == day]
            day_contexts = [row['context'].get('latest_context_percent') for row in matching
                            if isinstance(row.get('context'), dict)]
            day_contexts = [value for value in day_contexts if _number(value, high=100)]
            days.append({'date': datetime.fromtimestamp(day * 86400, timezone.utc).strftime('%Y-%m-%d'),
                         'samples': len(matching),
                         'peakContext': max(day_contexts) if day_contexts else None})
        return {
            'samples': len(rows),
            'spanSeconds': max(times) - min(times) if len(times) > 1 else 0,
            'minRemaining': min(remaining) if remaining else None,
            'peakContext': max(contexts) if contexts else None,
            'averageCachedShare': sum(cached) / len(cached) if cached else None,
            'models': sorted(by_model, key=lambda key: (-by_model[key], key))[:6],
            'weekly': {'timezone': 'UTC', 'days': days,
                       'modelCounts': [{'model': name, 'samples': count} for name, count in
                                       sorted(by_model.items(), key=lambda item: (-item[1], item[0]))[:6]]},
        }

    def enrich_quota(self, quota, now=None):
        """Add bounded pace estimates derived from numeric local samples."""
        if not isinstance(quota, dict):
            return quota
        now = self.clock() if now is None else now
        result = dict(quota)
        account_key = _account_key(quota)
        windows, budgets = [], []
        sources = quota.get('windows') if isinstance(quota.get('windows'), list) else []
        for source in sources:
            if not isinstance(source, dict):
                continue
            item, key = dict(source), source.get('key')
            series = []
            for row in self.rows:
                if account_key is None or row.get('accountKey') != account_key:
                    continue
                samples = row.get('windows') if isinstance(row.get('windows'), list) else []
                for sample in samples:
                    if (isinstance(sample, dict) and sample.get('key') == key and
                            _number(sample.get('remaining'), high=100) and _number(row.get('at'), 0)):
                        series.append((row['at'], sample['remaining']))
            if len(series) >= 2:
                first_at, first_remaining = series[0]
                last_at, last_remaining = series[-1]
                elapsed, consumed = last_at - first_at, first_remaining - last_remaining
                if elapsed > 0 and consumed > 0:
                    exhaust = max(0, last_remaining) * elapsed / consumed
                    if _number(exhaust):
                        item['exhaustInSec'] = exhaust
                        budgets.append(exhaust)
                        reset = item.get('resetsAt')
                        if _number(reset, 0) and reset > now and exhaust < reset - now:
                            item['projectedExhaustAt'] = now + exhaust
            duration, reset = item.get('duration'), item.get('resetsAt')
            if _number(duration, low=1) and _number(reset, 0) and reset >= now:
                expected = max(0, min(100, (reset - now) / (duration * 60) * 100))
                item['paceDelta'] = item.get('remaining', 0) - expected
            windows.append(item)
        result['windows'] = windows
        if budgets:
            result['budget'] = {'kind': 'exhaust', 'seconds': min(budgets)}
        return result
