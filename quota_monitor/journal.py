"""Combine bounded reads and per-file session state without retaining text."""
import hashlib
import os
from pathlib import Path

from .reader import JournalReader
from .session import SessionState
from .compat import thread_key
from .conversation_detail import ConversationDetail
from .health_state import HealthState


def project_identity(cwd):
    if not isinstance(cwd, str) or not 1 <= len(cwd) <= 2048 or '\0' in cwd or not os.path.isabs(cwd):
        return None
    normalized = os.path.normpath(cwd)
    name = Path(normalized).name
    if not name or len(name) > 80 or any(ord(char) < 32 for char in name):
        return None
    return {'projectKey': hashlib.sha256(normalized.encode('utf-8')).hexdigest(),
            'projectLabel': name}


class SessionJournal:
    def __init__(self, path, **limits):
        self.reader = JournalReader(path, **limits)
        self.state = SessionState()
        self.thread_id = None
        self.identity_status = 'missing'
        self.project = None
        self.detail = ConversationDetail()
        self.health = HealthState()

    def poll(self):
        batch = self.reader.poll()
        if batch.reset:
            self.state = SessionState()
            self.thread_id = None
            self.identity_status = 'missing'
            self.project = None
            self.detail.reset()
            self.health.reset()
        for record in batch.records:
            if record.get('type') == 'session_meta':
                payload = record.get('payload')
                value = payload.get('id') if isinstance(payload, dict) else None
                key = thread_key(value)
                if (self.identity_status == 'conflict' or key is None or key != value
                        or self.thread_id not in (None, key)):
                    self.thread_id = None
                    self.identity_status = 'conflict'
                    self.project = None
                else:
                    self.thread_id = key
                    self.identity_status = 'verified'
                    self.project = project_identity(payload.get('cwd'))
            self.state.accept(record)
            self.detail.accept(record)
            self.health.accept(record)
        detail = self.detail.snapshot(self.thread_id) if self.thread_id else None
        return {'session': self.state.snapshot(), 'status': batch.status,
                'thread_id': self.thread_id, 'identity_status': self.identity_status,
                'project': self.project,
                'reset': batch.reset, 'more': batch.more,
                'pending': batch.pending,
                'bytes_read': batch.bytes_read, 'invalid_lines': batch.invalid_lines,
                'detail': detail, 'health': self.health.snapshot()}
