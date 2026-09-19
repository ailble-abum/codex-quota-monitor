"""Project completed SessionJournal readings to the existing panel's fields.

Callers own the verified thread-to-file mapping. This adapter is not a file
discovery service or a replacement for the complete legacy payload builder.
"""
from .session import FIELDS


def thread_key(value):
    if not isinstance(value, str):
        return None
    key = value[6:] if value.startswith('local:') else value
    if not key or len(key) > 128:
        return None
    return key if all(c.isascii() and (c.isalnum() or c in '-_') for c in key) else None


def panel_summary(thread_id, reading):
    key = thread_key(thread_id)
    if key is None or reading['status'] != 'ok' or reading['more']:
        return None
    state = reading['session']
    result = {'thread_id': key, 'thread_keys': [key, 'local:' + key],
              'model': state.get('model'), 'reasoning_effort': state.get('effort'),
              'context_window': state.get('window'),
              'latest_context_tokens': state['last'].get('input_tokens'),
              'latest_context_percent': state.get('context_percent')}
    for source, prefix in (('last', 'latest_turn_'), ('total', 'session_')):
        for field in FIELDS:
            suffix = 'reasoning_tokens' if field == 'reasoning_output_tokens' else field
            result[prefix + suffix] = state[source].get(field)
    return result


def panel_payload(readings, active_thread_id):
    key = thread_key(active_thread_id)
    result = {'activeThreadId': key, 'selectedThreadId': None,
              'summaries': [], 'detail': None, 'detailsByThread': {}}
    # The legacy renderer may fall back to the first summary. Restrict this
    # bridge to the selected task so a failed lookup cannot show another task.
    if key is not None and key in readings:
        summary = panel_summary(key, readings[key])
        if summary is not None:
            result['summaries'] = [summary]
            result['selectedThreadId'] = key
    return result
