"""Combine bounded reads and per-file session state without retaining text."""
from .reader import JournalReader
from .session import SessionState


class SessionJournal:
    def __init__(self, path, **limits):
        self.reader = JournalReader(path, **limits)
        self.state = SessionState()

    def poll(self):
        batch = self.reader.poll()
        if batch.reset:
            self.state = SessionState()
        for record in batch.records:
            self.state.accept(record)
        return {'session': self.state.snapshot(), 'status': batch.status,
                'reset': batch.reset, 'more': batch.more,
                'bytes_read': batch.bytes_read, 'invalid_lines': batch.invalid_lines}
