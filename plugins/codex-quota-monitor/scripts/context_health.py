"""Compaction metadata only. Never treats request size as summary-only size."""
import json
from pathlib import Path

_cache = {}


def scan(path):
    path = Path(path)
    stat = path.stat()
    key = str(path)
    cached = _cache.get(key)
    if cached and cached[0] == (stat.st_mtime_ns, stat.st_size):
        return cached[1]
    events = []
    request = 0
    pending = None
    last = None
    window = None
    previous_usage = None
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            payload = row.get('payload') or {}
            if row.get('type') == 'compacted':
                pending = {'timestamp': row.get('timestamp'), 'before': last, 'after': None, 'request': request}
                events.append(pending)
            if row.get('type') == 'event_msg' and payload.get('type') == 'token_count':
                info = payload.get('info') or {}
                usage = info.get('last_token_usage') or {}
                current = usage.get('input_tokens')
                if not isinstance(current, int):
                    continue
                signature = json.dumps(info.get('total_token_usage') or usage, sort_keys=True)
                if signature != previous_usage:
                    request += 1
                    previous_usage = signature
                    if pending:
                        pending['after'] = current
                        pending = None
                last = current
                window = info.get('model_context_window') or window
    latest = events[-1] if events else None
    after = latest.get('after') if latest else None
    percent = after/window*100 if after is not None and window else None
    intervals = [b['request']-a['request'] for a,b in zip(events,events[1:])]
    frequent = len(intervals)>=2 and all(0<x<=5 for x in intervals[-2:])
    recommend = (percent is not None and percent>=40) or frequent
    result = {'count':len(events), 'after':after, 'afterPercent':percent,
              'latestAt':latest.get('timestamp') if latest else None,
              'intervals':intervals[-5:], 'recommendHandoff':recommend,
              'reason':'baseline' if percent is not None and percent>=40 else 'frequency' if frequent else None,
              'events':events[-20:]}
    _cache[key] = ((stat.st_mtime_ns,stat.st_size),result)
    if len(_cache)>20:
        _cache.pop(next(iter(_cache)))
    return result
