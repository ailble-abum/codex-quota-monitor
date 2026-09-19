"""Numeric projection of official rollout events; no message matching."""
FIELDS = ('input_tokens', 'cached_input_tokens', 'output_tokens',
          'reasoning_output_tokens', 'total_tokens')


def count(value):
    return value if type(value) is int and 0 <= value < 2**63 else None


def usage(value):
    data = value if isinstance(value, dict) else {}
    return {key: count(data.get(key)) for key in FIELDS}


def label(value):
    # Only model/effort identifiers belong here, never arbitrary event text.
    if isinstance(value, str) and 0 < len(value) <= 128:
        if all(c.isascii() and (c.isalnum() or c in '-_./:') for c in value):
            return value
    return None


class SessionState:
    def __init__(self):
        self.model = None
        self.effort = None
        self.total = usage(None)
        self.last = usage(None)
        self.window = None
        self.compactions = 0
        self.counter_resets = 0

    def accept(self, row):
        if not isinstance(row, dict) or not isinstance(row.get('payload'), dict):
            return
        payload = row['payload']
        kind = row.get('type')
        if kind == 'turn_context':
            model = label(payload.get('model'))
            if model != self.model:
                self.last = usage(None)
                self.window = None
            self.model = model
            self.effort = label(payload.get('effort'))
        elif kind == 'compacted':
            self.compactions += 1
            self.last = usage(None)
            self.window = None
        elif kind == 'event_msg' and payload.get('type') == 'token_count':
            info = payload.get('info')
            if not isinstance(info, dict):
                return
            incoming = usage(info.get('total_token_usage'))
            old, new = self.total['total_tokens'], incoming['total_tokens']
            if old is not None and new is not None and new < old:
                self.counter_resets += 1
            self.total = incoming
            self.last = usage(info.get('last_token_usage'))
            self.window = count(info.get('model_context_window')) or None

    def snapshot(self):
        tokens = self.last['input_tokens']
        percent = 100 * tokens / self.window if tokens is not None and self.window else None
        return {'model': self.model, 'effort': self.effort,
                'total': dict(self.total), 'last': dict(self.last),
                'window': self.window, 'context_percent': percent,
                'compactions': self.compactions, 'counter_resets': self.counter_resets}
