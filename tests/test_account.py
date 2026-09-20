import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

from quota_monitor import account


class AccountTests(unittest.IsolatedAsyncioTestCase):
    def test_projection(self):
        result = account.project({'rateLimits': {'primary': {'usedPercent': 25,
            'windowDurationMins': 300, 'resetsAt': 2000}, 'secondary': None,
            'planType': 'pro', 'credits': {'secret': 'hidden'}}}, now=1000)
        self.assertEqual(result['windows'], [{'key': 'primary', 'remaining': 75, 'duration': 300, 'resetsAt': 2000}])
        self.assertEqual(result['status'], 'live')
        self.assertNotIn('secret', json.dumps(result))

    def test_bucket_selection_and_invalid_data(self):
        for raw in ({}, {'rateLimitsByLimitId': {}, 'rateLimits': {'primary': {'usedPercent': 0}}},
                    {'rateLimits': {'primary': {'usedPercent': True}}},
                    {'rateLimits': {'primary': {'usedPercent': float('nan')}}}):
            self.assertEqual(account.project(raw, now=1000)['status'], 'unavailable')
        result = account.project({'rateLimitsByLimitId': {'codex': {'primary': None, 'secondary': None}}}, now=1000)
        self.assertEqual(result['windowStatus'], 'not_reported')

    async def test_real_stdio_handshake_and_whitelist(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / 'server.py'
            script.write_text('''import sys,json
first=json.loads(input()); assert first['method']=='initialize'
print(json.dumps({'id':first['id'],'result':{}}),flush=True)
assert json.loads(input())['method']=='initialized'
request=json.loads(input()); assert request['method']=='account/rateLimits/read'
print(json.dumps({'method':'noise','params':{'secret':'hidden'}}),flush=True)
print(json.dumps({'id':request['id'],'result':{'rateLimits':{'primary':{'usedPercent':42}}}}),flush=True)
input()
''')
            result = await account.read_account([sys.executable, str(script)], timeout=2)
            self.assertEqual(result['windows'][0]['remaining'], 58)
            self.assertNotIn('hidden', json.dumps(result))

    async def test_timeout_and_missing(self):
        result = await account.read_account([sys.executable, '-c', 'import time; time.sleep(20)'], timeout=.1)
        self.assertEqual(result['errorCode'], 'timeout')
        result = await account.read_account(['/nonexistent/quota-v2-cli'], timeout=.1)
        self.assertEqual(result['errorCode'], 'cli_missing')

    async def test_background_does_not_block_and_failure_clears(self):
        from unittest.mock import patch
        gate = asyncio.Event()
        async def read(*args, **kwargs):
            await gate.wait()
            return account.unavailable('app_server')
        with patch.object(account, 'read_account', read):
            source = account.AccountSource('/example/cli')
            source.value = {'status': 'live', 'updatedAt': 1, 'windows': [{'remaining': 100}]}
            self.assertEqual(source.snapshot()['status'], 'unavailable')
            gate.set()
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            self.assertEqual(source.snapshot()['windows'], [])
            await source.close()

    async def test_runtime_publishes_account_and_closes_source(self):
        from unittest.mock import patch, AsyncMock
        from quota_monitor.runtime import UpdateLoop
        loop = UpdateLoop('http://127.0.0.1:9222', 'about:blank', {}, account_cli='/example/codex')
        quota = {'status': 'live', 'updatedAt': 1000, 'windows': []}
        loop.account.snapshot = lambda: quota
        loop.account.close = AsyncMock()
        client = AsyncMock()
        client.endpoint = 'ws://127.0.0.1:9222/devtools/page/one'
        client.evaluate.side_effect = ['one', True]
        loop.client = client
        with patch('quota_monitor.runtime.list_pages', return_value=[]), patch('quota_monitor.runtime.select_page', return_value=client.endpoint):
            self.assertEqual(await loop.step(), 'updated')
        expression = client.evaluate.call_args.args[0]
        self.assertIn('"quota": {"status": "live"', expression)
        client.evaluate.side_effect = None
        client.evaluate.return_value = True
        await loop.shutdown()
        loop.account.close.assert_awaited_once()

    def test_large_numbers_and_explicit_block(self):
        for percent in (10**400, -1, 101, '25', None):
            self.assertEqual(account.project({'rateLimits': {'primary': {'usedPercent': percent}}}, now=1)['status'], 'unavailable')
        result = account.project({'rateLimits': {'primary': {'usedPercent': 1}, 'rateLimitReachedType': 'weekly'}}, now=1)
        self.assertFalse(result['ordinaryUsageAllowed'])

    async def test_cancellation_reaps_child(self):
        from unittest.mock import patch
        original = asyncio.create_subprocess_exec
        children = []
        async def start(*args, **kwargs):
            child = await original(*args, **kwargs)
            children.append(child)
            return child
        with patch.object(asyncio, 'create_subprocess_exec', start):
            task = asyncio.create_task(account.read_account([sys.executable, '-c', 'import time; time.sleep(20)']))
            while not children:
                await asyncio.sleep(.01)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertIsNotNone(children[0].returncode)

    def test_explicit_cli_configuration(self):
        from quota_monitor.live import load_config
        from quota_monitor.runtime import UpdateLoop
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps({'origin':'http://127.0.0.1:9222', 'page_url':'about:blank',
                'journals':{'one':'one.jsonl'}, 'account_cli':'/explicit/codex'}))
            loop = UpdateLoop(**load_config(path))
            self.assertEqual(loop.account.command, ['/explicit/codex', 'app-server'])
        for value in ('relative', '', True, [], '/bad\0path'):
            with self.assertRaises(ValueError):
                UpdateLoop('http://127.0.0.1:9222', 'about:blank', {}, account_cli=value)
