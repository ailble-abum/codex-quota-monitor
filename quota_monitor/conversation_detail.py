"""Bounded assistant-message details for the V2 panel.

This is a small, numeric-first projection. It reads only records already
accepted by ``SessionJournal`` and never publishes raw event payloads.
"""

from .session import count, usage


MAX_MESSAGES = 160
MAX_ASSISTANT_ITEMS = 40
MAX_TEXT_PREFIX = 120


def _text(payload):
    content = payload.get('content') if isinstance(payload, dict) else None
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ''
    parts = [item.get('text', '') for item in content
             if isinstance(item, dict) and isinstance(item.get('text'), str)]
    return '\n\n'.join(parts).strip()


def _visible(role, text):
    if role != 'user':
        return True
    value = text.lstrip()
    return not (value.startswith('<environment_context>')
                or value.startswith('<permissions instructions>'))


def _prefix(value):
    return ' '.join(value.split())[:MAX_TEXT_PREFIX]


def _message_usage(info):
    if not isinstance(info, dict):
        return None
    last = usage(info.get('last_token_usage'))
    window = count(info.get('model_context_window'))
    context = last.get('input_tokens')
    percent = 100 * context / window if context is not None and window else None
    total_usage = info.get('total_token_usage')
    total_tokens = total_usage.get('total_tokens') if isinstance(total_usage, dict) else None
    return {
        'context_window': window,
        'latest_context_tokens': context,
        'latest_context_percent': percent,
        'latest_turn_total_tokens': last.get('total_tokens'),
        'latest_turn_input_tokens': last.get('input_tokens'),
        'latest_turn_cached_input_tokens': last.get('cached_input_tokens'),
        'latest_turn_output_tokens': last.get('output_tokens'),
        'latest_turn_reasoning_tokens': last.get('reasoning_output_tokens'),
        'session_total_tokens': count(total_tokens),
    }


class ConversationDetail:
    """Track just enough message structure to place safe Token chips."""

    def __init__(self):
        self.messages = []
        self.pending_assistant = None
        self.turns = 0
        self.assistants = 0

    def reset(self):
        self.__init__()

    def accept(self, row):
        if not isinstance(row, dict):
            return
        payload = row.get('payload')
        if row.get('type') == 'response_item' and isinstance(payload, dict):
            if payload.get('type') != 'message':
                return
            role = payload.get('role')
            if role not in ('user', 'assistant'):
                return
            text = _text(payload)
            if not _visible(role, text):
                return
            if role == 'user':
                self.pending_assistant = None
                self.turns += 1
            else:
                self.assistants += 1
            item = {
                'role': role,
                'textPrefix': _prefix(text),
                'turnIndex': self.turns if role == 'assistant' else None,
                'usage': None,
                'timestamp': row.get('timestamp') if isinstance(row.get('timestamp'), str) else None,
            }
            self.messages.append(item)
            if role == 'assistant':
                self.pending_assistant = len(self.messages) - 1
            self._trim()
            return
        if (row.get('type') == 'event_msg' and isinstance(payload, dict)
                and payload.get('type') == 'token_count'
                and self.pending_assistant is not None):
            info = payload.get('info')
            current = _message_usage(info)
            if current is not None and self.pending_assistant < len(self.messages):
                self.messages[self.pending_assistant]['usage'] = current
            self.pending_assistant = None

    def _trim(self):
        if len(self.messages) <= MAX_MESSAGES:
            return
        removed = len(self.messages) - MAX_MESSAGES
        self.messages = self.messages[removed:]
        if self.pending_assistant is not None:
            self.pending_assistant -= removed
            if self.pending_assistant < 0:
                self.pending_assistant = None

    def snapshot(self, thread_id, updated_at=None):
        assistants = [item for item in self.messages
                      if item['role'] == 'assistant' and item.get('usage')]
        assistants = assistants[-MAX_ASSISTANT_ITEMS:]
        total = self.assistants
        start = max(0, total - len(assistants))
        items = []
        for index, item in enumerate(assistants, start=1):
            usage_data = dict(item['usage'])
            items.append({
                'textPrefix': item['textPrefix'],
                'tokenUsage': usage_data,
                'roundIndex': item.get('turnIndex') or index,
                'totalRounds': self.turns or total,
                'assistantTurnIndex': start + index,
                'assistantTotalTurns': total,
            })
        return {'thread_id': thread_id, 'updated_at': updated_at,
                'assistantItems': items}
