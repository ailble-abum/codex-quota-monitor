"""Edit only Codex's two global context defaults through its official RPC."""
import asyncio
import re

from .account import resolve_cli
from .app_server import AppServer

KEYS = ('model_context_window', 'model_auto_compact_token_limit')
MAX_TOKENS = 2147483647


def tokens(value):
    return value is None or type(value) is int and 1 <= value <= MAX_TOKENS


def project(raw):
    """Discard all other configuration, paths, instructions and credentials."""
    if not isinstance(raw, dict) or not isinstance(raw.get('config'), dict):
        raise ValueError('invalid config')
    layers = raw.get('layers')
    if not isinstance(layers, list):
        raise ValueError('missing config layers')
    users = [row for row in layers if isinstance(row, dict) and
             isinstance(row.get('name'), dict) and row['name'].get('type') == 'user'
             and row['name'].get('profile') is None and not row.get('disabledReason')]
    revision = users[0].get('version') if len(users) == 1 else None
    if not isinstance(revision, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', revision):
        raise ValueError('missing user revision')
    config = raw['config']
    values = [config.get(key) for key in KEYS]
    if not all(tokens(value) for value in values):
        raise ValueError('invalid context defaults')
    result = {'status': 'ready', 'revision': users[0]['version'],
              'windowTokens': values[0], 'compactTokens': values[1]}
    model = config.get('model')
    if isinstance(model, str) and 0 < len(model) <= 128:
        result['model'] = model
    return result


def validate(request):
    if not isinstance(request, dict) or not isinstance(request.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', request['id']):
        raise ValueError('invalid request')
    action = request.get('action')
    expected = {'id', 'action'} if action == 'read' else {'id', 'action', 'revision'}
    if action == 'save':
        expected |= {'windowTokens', 'compactTokens'}
        window, compact = request.get('windowTokens'), request.get('compactTokens')
        if not tokens(window) or not tokens(compact) or window is not None and compact is not None and compact >= window:
            raise ValueError('invalid token limits')
    if action not in ('read', 'save', 'reset') or set(request) != expected:
        raise ValueError('invalid action')
    if action != 'read' and (not isinstance(request.get('revision'), str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', request['revision'])):
        raise ValueError('invalid revision')


async def exchange(command, request, *, env=None, timeout=12):
    validate(request)
    async def run():
        async with AppServer(command, env=env) as server:
            state = project(await server.request('config/read', {'includeLayers': True}))
            if request['action'] != 'read':
                if state['revision'] != request['revision']:
                    return dict(state, requestId=request['id'], feedback='conflict')
                values = [None, None] if request['action'] == 'reset' else [request['windowTokens'], request['compactTokens']]
                written = await server.request('config/batchWrite', {
                    'edits': [{'keyPath': key, 'value': value, 'mergeStrategy': 'replace'}
                              for key, value in zip(KEYS, values)],
                    'expectedVersion': request['revision'], 'reloadUserConfig': False})
                if not isinstance(written, dict) or written.get('status') not in ('ok', 'okOverridden'):
                    raise ValueError('invalid write response')
                state = project(await server.request('config/read', {'includeLayers': True}))
                state['feedback'] = 'overridden' if written['status'] == 'okOverridden' else 'saved'
            return dict(state, requestId=request['id'])
    return await asyncio.wait_for(run(), timeout)


class ContextDefaultsSource:
    """Lazy reads and one user-requested edit at a time, independent of quota."""
    def __init__(self, cli):
        self.cli, self.task = cli, None
        self.value = {'status': 'idle'}

    def snapshot(self):
        return self.value

    def request(self, request):
        if self.task is not None and not self.task.done():
            return False
        try:
            validate(request)
        except (ValueError, TypeError):
            return False
        self.value = dict(self.value, status='busy', requestId=request['id'], feedback='')
        self.task = asyncio.create_task(self._run(request.copy()))
        return True

    async def _run(self, request):
        try:
            self.value = await exchange([resolve_cli(self.cli), 'app-server'], request)
        except (OSError, ValueError, TypeError, RecursionError, asyncio.TimeoutError):
            # A write timeout may happen after the write. Never auto-retry it.
            self.value = {'status': 'unavailable', 'requestId': request['id'],
                          'feedback': 'read_failed' if request['action'] == 'read' else 'write_unconfirmed'}

    async def close(self):
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
