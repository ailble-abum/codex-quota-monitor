"""Numeric compaction health derived from the V2 journal stream."""

from .session import count, usage


def _token_info(row):
    payload = row.get('payload') if isinstance(row, dict) else None
    if not isinstance(payload, dict) or payload.get('type') != 'token_count':
        return None
    info = payload.get('info')
    return info if isinstance(info, dict) else None


class HealthState:
    def __init__(self):
        self.events = []
        self.pending = None
        self.requests = 0
        self.last_input = None
        self.window = None
        self.signature = None

    def reset(self):
        self.__init__()

    def accept(self, row):
        if not isinstance(row, dict):
            return
        if row.get('type') == 'compacted':
            event = {'request': self.requests, 'before': self.last_input,
                     'after': None, 'timestamp': self._timestamp(row)}
            self.events.append(event)
            self.pending = event
            self.events = self.events[-20:]
            if self.pending not in self.events:
                self.pending = self.events[-1]
            return
        info = _token_info(row)
        if info is None:
            return
        last = usage(info.get('last_token_usage'))
        current = last.get('input_tokens')
        window = count(info.get('model_context_window'))
        signature = tuple(last.get(key) for key in (
            'input_tokens', 'cached_input_tokens', 'output_tokens',
            'reasoning_output_tokens', 'total_tokens')) + (window,)
        if signature != self.signature:
            self.requests += 1
            self.signature = signature
            if self.pending is not None:
                self.pending['after'] = current
                self.pending = None
        self.last_input, self.window = current, window

    @staticmethod
    def _timestamp(row):
        value = row.get('timestamp')
        return value[:128] if isinstance(value, str) else None

    def snapshot(self):
        latest = self.events[-1] if self.events else None
        intervals = [right['request'] - left['request']
                     for left, right in zip(self.events, self.events[1:])]
        after = latest.get('after') if latest else None
        percent = 100 * after / self.window if after is not None and self.window else None
        frequent = len(intervals) >= 2 and all(0 < value <= 5 for value in intervals[-2:])
        baseline = percent is not None and percent >= 40
        return {'count': len(self.events), 'after': after, 'afterPercent': percent,
                'latestAt': latest.get('timestamp') if latest else None,
                'intervals': intervals[-5:], 'recommendHandoff': baseline or frequent,
                'reason': 'baseline' if baseline else 'frequency' if frequent else None}
