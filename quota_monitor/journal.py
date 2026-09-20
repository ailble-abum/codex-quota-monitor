"""Combine bounded reads and per-file session state without retaining text."""
from .reader import JournalReader
from .session import SessionState
from .compat import thread_key
from .conversation_detail import ConversationDetail


class SessionJournal:
    def __init__(self, path, **limits):
        self.reader = JournalReader(path, **limits)
        self.state = SessionState()
        self.thread_id = None
        self.identity_status = 'missing'
        self.detail = ConversationDetail()

    def poll(self):
        batch = self.reader.poll()
        if batch.reset:
            self.state = SessionState()
            self.thread_id = None
            self.identity_status = 'missing'
            self.detail.reset()
        for record in batch.records:
            if record.get('type') == 'session_meta':
                payload = record.get('payload')
                value = payload.get('id') if isinstance(payload, dict) else None
                key = thread_key(value)
                if (self.identity_status == 'conflict' or key is None or key != value
                        or self.thread_id not in (None, key)):
                    self.thread_id = None
                    self.identity_status = 'conflict'
                else:
                    self.thread_id = key
                    self.identity_status = 'verified'
            self.state.accept(record)
            self.detail.accept(record)
        detail = self.detail.snapshot(self.thread_id) if self.thread_id else None
        return {'session': self.state.snapshot(), 'status': batch.status,
                'thread_id': self.thread_id, 'identity_status': self.identity_status,
                'reset': batch.reset, 'more': batch.more,
                'pending': batch.pending,
                'bytes_read': batch.bytes_read, 'invalid_lines': batch.invalid_lines,
                'detail': detail}
