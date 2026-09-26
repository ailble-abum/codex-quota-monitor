"""Project completed SessionJournal readings to the existing panel's fields.

Journal metadata must agree with the selected task. This adapter is not a file
discovery service or a replacement for the complete legacy payload builder.
"""
from .session import FIELDS
import time


def thread_key(value):
    if not isinstance(value, str):
        return None
    key = value[6:] if value.startswith('local:') else value
    if not key or len(key) > 128:
        return None
    return key if all(c.isascii() and (c.isalnum() or c in '-_') for c in key) else None


def panel_summary(thread_id, reading, *, allow_partial=False):
    key = thread_key(thread_id)
    if key is None or reading['status'] != 'ok' or (reading['more'] and not allow_partial):
        return None
    if reading.get('identity_status') != 'verified' or reading.get('thread_id') != key:
        return None
    state = reading['session']
    result = {'thread_id': key, 'thread_keys': [key, 'local:' + key],
              'model': state.get('model'), 'reasoning_effort': state.get('effort'),
              'context_window': state.get('window'),
              'latest_context_tokens': state['last'].get('input_tokens'),
              'latest_context_percent': state.get('context_percent')}
    health = reading.get('health')
    if isinstance(health, dict):
        # Sidebar summaries need only the count, post-request token marker and
        # percentage. Do not reuse the selected task's richer health projection.
        result['compaction_count'] = health.get('count')
        result['post_compaction_tokens'] = health.get('after')
        result['post_compaction_percent'] = health.get('afterPercent')
    project = reading.get('project')
    if isinstance(project, dict):
        project_key, project_label = project.get('projectKey'), project.get('projectLabel')
        if (isinstance(project_key, str) and len(project_key) == 64 and
                all(char in '0123456789abcdef' for char in project_key) and
                isinstance(project_label, str) and 0 < len(project_label) <= 80 and
                '/' not in project_label and '\\' not in project_label and
                all(ord(char) >= 32 for char in project_label)):
            result.update(projectKey=project_key, projectLabel=project_label)
    for source, prefix in (('last', 'latest_turn_'), ('total', 'session_')):
        for field in FIELDS:
            suffix = 'reasoning_tokens' if field == 'reasoning_output_tokens' else field
            result[prefix + suffix] = state[source].get(field)
    return result


def panel_payload(readings, active_thread_id, *, allow_partial=False):
    key = thread_key(active_thread_id)
    result = {'activeThreadId': key, 'selectedThreadId': None, 'observedAt': time.time(),
              'summaries': [], 'detail': None, 'detailsByThread': {},
              'health': None, 'healthThreadId': None}
    # Every summary is identity-verified by the source. The selected task still
    # owns detail/health, while other summaries are numeric-only sidebar data.
    if key is not None and key in readings:
        summary = panel_summary(key, readings[key], allow_partial=allow_partial)
        if summary is not None:
            summaries = []
            for candidate, reading in readings.items():
                projected = panel_summary(candidate, reading,
                                          allow_partial=allow_partial and candidate == key)
                if projected is not None:
                    summaries.append(projected)
            result['summaries'] = summaries
            result['selectedThreadId'] = key
            health = readings[key].get('health')
            if isinstance(health, dict):
                result['health'] = {name: health.get(name) for name in (
                    'count', 'after', 'afterPercent', 'latestAt', 'intervals',
                    'recommendHandoff', 'reason')}
                result['healthThreadId'] = key
            detail = readings[key].get('detail')
            if isinstance(detail, dict) and detail.get('thread_id') == key:
                # The detail projection is deliberately limited to assistant
                # prefixes and validated numeric usage; raw event rows never
                # cross this boundary.
                safe_items = []
                for item in detail.get('assistantItems', []):
                    if not isinstance(item, dict) or not isinstance(item.get('tokenUsage'), dict):
                        continue
                    usage = item['tokenUsage']
                    safe_items.append({
                        'textPrefix': item.get('textPrefix') if isinstance(item.get('textPrefix'), str) else '',
                        'tokenUsage': {name: usage.get(name) for name in (
                            'context_window', 'latest_context_tokens', 'latest_context_percent',
                            'latest_turn_total_tokens', 'latest_turn_input_tokens',
                            'latest_turn_cached_input_tokens', 'latest_turn_output_tokens',
                            'latest_turn_reasoning_tokens', 'session_total_tokens')},
                        'roundIndex': item.get('roundIndex'),
                        'totalRounds': item.get('totalRounds'),
                        'assistantTurnIndex': item.get('assistantTurnIndex'),
                        'assistantTotalTurns': item.get('assistantTotalTurns'),
                    })
                projected = {'thread_id': key, 'assistantItems': safe_items}
                result['detail'] = projected
                result['detailsByThread'][key] = projected
                result['detailsByThread']['local:' + key] = projected
    return result
