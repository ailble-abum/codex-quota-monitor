import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from quota_monitor import context_defaults as defaults
from quota_monitor import runtime

REVISION = 'sha256:' + 'a' * 64
NEW_REVISION = 'sha256:' + 'b' * 64


def config(revision=REVISION, window=200000, compact=170000):
    return {'config': {'model': 'synthetic-model', 'model_context_window': window,
                      'model_auto_compact_token_limit': compact,
                      'model_providers': {'private': {'experimental_bearer_token': 'SECRET'}}},
            'layers': [{'name': {'type': 'user', 'file': '/private/config.toml'},
                        'version': revision, 'config': {'secret': 'SECRET'}}]}


class ProjectionTests(unittest.TestCase):
    def test_projection_drops_credentials_paths_and_instructions(self):
        result = defaults.project(config())
        self.assertEqual(result, {'status': 'ready', 'revision': REVISION,
            'model': 'synthetic-model', 'windowTokens': 200000, 'compactTokens': 170000})
        self.assertNotIn('SECRET', str(result))
        self.assertNotIn('/private', str(result))

    def test_exact_request_allowlist_and_integer_limits(self):
        base = {'id': 'one', 'action': 'save', 'revision': REVISION,
                'windowTokens': 200000, 'compactTokens': 170000}
        defaults.validate(base)
        defaults.validate(dict(base, windowTokens=None, compactTokens=None))
        for changes in ({'filePath': '/elsewhere'}, {'model': 'other'},
                        {'revision': None}, {'windowTokens': True}, {'windowTokens': 0},
                        {'compactTokens': float('nan')}, {'compactTokens': 200000},
                        {'compactTokens': '170000'}, {'windowTokens': defaults.MAX_TOKENS + 1},
                        {'action': 'login'}, {'id': []}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                defaults.validate(dict(base, **changes))

    def test_missing_ambiguous_and_profile_only_layers_are_not_editable(self):
        for layers in ([], config()['layers'] * 2,
                       [{'name': {'type': 'user', 'profile': 'custom'}, 'version': REVISION}]):
            with self.assertRaises(ValueError):
                defaults.project(dict(config(), layers=layers))
        for value in (-1, True, '200000', float('inf')):
            with self.assertRaises(ValueError):
                defaults.project(config(window=value))
        malformed = config()
        malformed['layers'][0]['version'] = None
        with self.assertRaises(ValueError):
            defaults.project(malformed)


class ExchangeTests(unittest.IsolatedAsyncioTestCase):
    def server(self, responses):
        server = AsyncMock()
        server.__aenter__.return_value = server
        server.request.side_effect = responses
        return server

    async def test_save_uses_atomic_two_key_rpc_and_version_without_hot_reload(self):
        server = self.server([config(), {'status': 'ok'}, config(NEW_REVISION, 180000, 150000)])
        request = {'id': 'one', 'action': 'save', 'revision': REVISION,
                   'windowTokens': 180000, 'compactTokens': 150000}
        with patch.object(defaults, 'AppServer', return_value=server):
            result = await defaults.exchange(['fake-cli'], request)
        self.assertEqual(result['feedback'], 'saved')
        self.assertEqual(result['revision'], NEW_REVISION)
        calls = server.request.call_args_list
        self.assertEqual([call.args[0] for call in calls], ['config/read', 'config/batchWrite', 'config/read'])
        self.assertEqual(calls[1].args[1], {'edits': [
            {'keyPath': 'model_context_window', 'value': 180000, 'mergeStrategy': 'replace'},
            {'keyPath': 'model_auto_compact_token_limit', 'value': 150000, 'mergeStrategy': 'replace'}],
            'expectedVersion': REVISION, 'reloadUserConfig': False})

    async def test_stale_revision_never_writes(self):
        server = self.server([config(NEW_REVISION)])
        with patch.object(defaults, 'AppServer', return_value=server):
            result = await defaults.exchange(['fake-cli'], {'id': 'reset', 'action': 'reset', 'revision': REVISION})
        self.assertEqual(result['feedback'], 'conflict')
        self.assertEqual(server.request.await_count, 1)

    async def test_reset_deletes_only_two_keys_and_reports_overrides(self):
        server = self.server([config(), {'status': 'okOverridden'}, config(NEW_REVISION)])
        with patch.object(defaults, 'AppServer', return_value=server):
            result = await defaults.exchange(['fake-cli'], {'id': 'reset', 'action': 'reset', 'revision': REVISION})
        self.assertEqual(result['feedback'], 'overridden')
        self.assertEqual([edit['value'] for edit in server.request.call_args_list[1].args[1]['edits']], [None, None])

    async def test_source_is_lazy_single_flight_and_write_timeout_requires_readback(self):
        source = defaults.ContextDefaultsSource('/fake/cli')
        self.assertIsNone(source.task)
        request = {'id': 'one', 'action': 'reset', 'revision': REVISION}
        gate = asyncio.Event()
        async def timeout(*args):
            await gate.wait()
            raise asyncio.TimeoutError()
        with patch.object(defaults, 'exchange', side_effect=timeout) as rpc:
            self.assertTrue(source.request(request))
            self.assertFalse(source.request(request))
            request['revision'] = 'mutated-after-submit'
            gate.set()
            await source.task
            self.assertEqual(rpc.call_args.args[1]['revision'], REVISION)
            self.assertEqual(source.value['feedback'], 'write_unconfirmed')
            self.assertEqual(rpc.call_count, 1)
        self.assertFalse(source.request({'id': 'bad', 'action': 'login'}))
        with patch.object(defaults, 'exchange', AsyncMock(return_value=defaults.project(config()))):
            self.assertTrue(source.request({'id': 'refresh', 'action': 'read'}))
            await source.task
        self.assertEqual(source.value['status'], 'ready')
        await source.close()

    async def test_read_failure_does_not_leak_error_text(self):
        source = defaults.ContextDefaultsSource('/fake/cli')
        with patch.object(defaults, 'exchange', AsyncMock(side_effect=OSError('SECRET'))):
            source.request({'id': 'one', 'action': 'read'})
            await source.task
        self.assertEqual(source.value, {'status': 'unavailable', 'requestId': 'one', 'feedback': 'read_failed'})

    async def test_shutdown_cancels_pending_settings_query(self):
        source = defaults.ContextDefaultsSource('/fake/cli')
        started = asyncio.Event()
        stopped = asyncio.Event()
        async def wait(*args):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
        with patch.object(defaults, 'exchange', side_effect=wait):
            source.request({'id': 'one', 'action': 'read'})
            await started.wait()
            await source.close()
        self.assertTrue(stopped.is_set())
        self.assertTrue(source.task.cancelled())

    async def test_runtime_keeps_settings_separate_from_context_and_quota(self):
        loop = runtime.UpdateLoop('http://127.0.0.1:9222', 'about:blank', {}, panel=True, account_cli='/fake/codex')
        loop.account.snapshot = Mock(return_value={'status': 'unavailable', 'windows': []})
        loop.update.snapshot = Mock(return_value={'status': 'unavailable'})
        loop.context_defaults.request = Mock()
        loop.context_defaults.value = defaults.project(config())
        client = AsyncMock()
        client.endpoint = 'ws://127.0.0.1:9222/devtools/page/one'
        loop.client = client
        request = {'id': 'one', 'action': 'read'}
        for key, context, expected in [('one', None, 'ready'), (None, 'chatgpt', 'not_applicable')]:
            # read, optional contextSource, settings request, quota refresh, updates, publish
            client.evaluate.side_effect = [key] + ([context] if context else []) + [request, False, False, False, True]
            with patch.object(runtime, 'list_pages', return_value=[]), patch.object(runtime, 'select_page', return_value=client.endpoint):
                self.assertEqual(await loop.step(), 'updated')
            import json
            payload = json.loads(client.evaluate.call_args.args[0][len(runtime._PAGE_BRIDGE)+1:-1])['payload']
            self.assertEqual(payload['contextDefaults']['status'], expected)
            self.assertEqual(payload['quota']['status'], 'unavailable')
        loop.context_defaults.request.assert_called_once_with(request)
        await loop.context_defaults.close()

    async def test_runtime_requires_explicit_matching_saved_revision_to_restart(self):
        from quota_monitor.host_restart import HostRestartSource
        loop = runtime.UpdateLoop('http://127.0.0.1:9222', 'about:blank', {}, panel=True, account_cli='/fake/codex')
        loop.account.snapshot = Mock(return_value={'status': 'unavailable', 'windows': []})
        loop.update.snapshot = Mock(return_value={'status': 'unavailable'})
        loop.context_defaults.value = dict(defaults.project(config()), feedback='saved')
        restarter = Mock()
        restarter.restart.return_value = 'reopened'
        loop.context_restart = HostRestartSource(restarter)
        client = AsyncMock()
        client.endpoint = 'ws://127.0.0.1:9222/devtools/page/one'
        loop.client = client
        for request in (None, {'revision': NEW_REVISION}, {'revision': REVISION, 'app': '/other'}, {'revision': REVISION}):
            client.evaluate.side_effect = ['one', None, request, False, False, False, True]
            with patch.object(runtime, 'list_pages', return_value=[]), patch.object(runtime, 'select_page', return_value=client.endpoint):
                self.assertEqual(await loop.step(), 'updated')
            if request != {'revision': REVISION}:
                self.assertIsNone(loop.context_restart.task)
        await loop.context_restart.task
        restarter.restart.assert_called_once()
        await loop.context_restart.close()
