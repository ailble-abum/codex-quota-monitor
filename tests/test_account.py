import asyncio
import hashlib
import json
import os
import signal
import sys
import tempfile
import unittest
from pathlib import Path

from quota_monitor import account


class AccountTests(unittest.IsolatedAsyncioTestCase):
    @unittest.skipIf(os.name != 'posix', 'POSIX child process group cleanup')
    async def test_account_cleanup_kills_descendants_and_finishes_within_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pid_file = root / 'child.pid'
            script = root / 'server.py'
            script.write_text('''import json,subprocess,sys,pathlib
child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(20)'])
pathlib.Path(sys.argv[1]).write_text(str(child.pid))
request=json.loads(input())
print(json.dumps({'id':request['id'],'result':{}}),flush=True)
input()
request=json.loads(input())
print(json.dumps({'id':request['id'],'result':{'rateLimits':{'primary':{'usedPercent':25}}}}),flush=True)
request=json.loads(input())
print(json.dumps({'id':request['id'],'error':{'code':-32601}}),flush=True)
import time;time.sleep(20)
''')
            try:
                result = await asyncio.wait_for(account.read_account(
                    [sys.executable, str(script), str(pid_file)], timeout=1), 3)
                self.assertEqual(result['status'], 'live')
                gone = False
                for _ in range(30):
                    try:
                        os.kill(int(pid_file.read_text()), 0)
                    except ProcessLookupError:
                        gone = True
                        break
                    await asyncio.sleep(.01)
                self.assertTrue(gone, 'account refresh must not leave its child process running')
            finally:
                if pid_file.exists():
                    try:
                        os.kill(int(pid_file.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    async def test_failure_retries_without_restart_then_returns_to_minute_polling(self):
        from unittest.mock import AsyncMock, patch
        from types import SimpleNamespace
        source = account.AccountSource('/example/cli')
        clock = [100.0]
        live = {'status': 'live', 'updatedAt': 1000, 'windows': []}
        read = AsyncMock(side_effect=[account.unavailable('timeout'),
                                     account.unavailable('app_server'), live])
        with patch.object(account, 'time', SimpleNamespace(monotonic=lambda: clock[0], time=lambda: 1000)), \
                patch.object(account, 'read_account', read):
            source.snapshot()
            await source.task
            self.assertEqual(source.next_read, 105)
            clock[0] = 104
            source.snapshot()
            self.assertEqual(read.await_count, 1)
            clock[0] = 105
            source.snapshot()
            await source.task
            self.assertEqual(source.next_read, 115)
            clock[0] = 115
            source.snapshot()
            await source.task
            self.assertEqual(source.snapshot()['status'], 'live')
            self.assertEqual(source.failures, 0)
            self.assertEqual(source.next_read, 175)
            await source.close()

    async def test_refresh_error_is_contained_and_manual_refresh_resets_backoff(self):
        from unittest.mock import AsyncMock, patch
        source = account.AccountSource('/example/cli')
        with patch.object(account, 'read_account', AsyncMock(side_effect=OSError('private'))):
            for _ in range(10):
                await source.refresh()
            self.assertEqual(source.value, account.unavailable('app_server'))
            self.assertEqual(source.failures, 5)
            self.assertLessEqual(source.next_read - account.time.monotonic(), 60)
            source.request_refresh()
            self.assertEqual(source.failures, 0)
            self.assertEqual(source.next_read, 0)

    def test_server_usage_decision_takes_precedence_and_unknown_is_preserved(self):
        for allowed in (True, False, None):
            value = account.project({'ordinaryUsageAllowed': allowed,
                'rateLimits': {'primary': {'usedPercent': 1}}}, now=1)
            self.assertIs(value['ordinaryUsageAllowed'], allowed)
        self.assertEqual(account.project({'ordinaryUsageAllowed': 'true',
            'rateLimits': {'primary': {'usedPercent': 1}}}, now=1)['status'], 'unavailable')

    def test_cli_resolves_known_packaging_only_within_configured_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            resources = Path(directory) / 'Codex.app/Contents/Resources'
            legacy = resources / 'codex'
            bundled = resources / 'codex-cli/CodexCLI.app/Contents/MacOS/codex'
            bundled.parent.mkdir(parents=True)
            bundled.write_text('#!/bin/sh\nexit 0\n')
            bundled.chmod(0o755)
            self.assertEqual(account.resolve_cli(str(legacy)), str(bundled))
            legacy.write_text('#!/bin/sh\nexit 0\n')
            legacy.chmod(0o755)
            self.assertEqual(account.resolve_cli(str(legacy)), str(legacy))
            custom = resources / 'custom/codex'
            self.assertEqual(account.resolve_cli(str(custom)), str(custom))
            other = Path(directory) / 'Other.app/Contents/Resources/codex'
            self.assertEqual(account.resolve_cli(str(other)), str(other))

    def test_cli_wrapper_fallback_requires_executable_file(self):
        with tempfile.TemporaryDirectory() as directory:
            resources = Path(directory) / 'Codex.app/Contents/Resources'
            legacy = resources / 'codex'
            wrapper = resources / 'codex-cli/bin/codex'
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text('#!/bin/sh\nexit 0\n')
            wrapper.chmod(0o644)
            self.assertEqual(account.resolve_cli(str(legacy)), str(legacy))
            wrapper.chmod(0o755)
            self.assertEqual(account.resolve_cli(str(legacy)), str(wrapper))

    async def test_cli_packaging_is_resolved_again_after_app_update(self):
        from unittest.mock import AsyncMock, patch
        with tempfile.TemporaryDirectory() as directory:
            resources = Path(directory) / 'Codex.app/Contents/Resources'
            resources.mkdir(parents=True)
            legacy = resources / 'codex'
            legacy.write_text('#!/bin/sh\nexit 0\n')
            legacy.chmod(0o755)
            source = account.AccountSource(str(legacy))
            with patch.object(account, 'read_account', new_callable=AsyncMock,
                              return_value=account.unavailable()) as read:
                await source.refresh()
                read.assert_awaited_with([str(legacy), 'app-server'])
                legacy.unlink()
                bundled = resources / 'codex-cli/CodexCLI.app/Contents/MacOS/codex'
                bundled.parent.mkdir(parents=True)
                bundled.write_text('#!/bin/sh\nexit 0\n')
                bundled.chmod(0o755)
                await source.refresh()
                read.assert_awaited_with([str(bundled), 'app-server'])

    def test_projection(self):
        result = account.project({'accountId': 'private-account', 'rateLimits': {'primary': {'usedPercent': 25,
            'windowDurationMins': 300, 'resetsAt': 2000}, 'secondary': None,
            'planType': 'pro', 'credits': {'secret': 'hidden'}}}, now=1000)
        self.assertEqual(result['windows'], [{'key': 'primary', 'remaining': 75, 'duration': 300, 'resetsAt': 2000}])
        self.assertEqual(result['status'], 'live')
        self.assertEqual(result['accountKey'], hashlib.sha256(b'private-account').hexdigest())
        self.assertNotIn('private-account', json.dumps(result))
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
request=json.loads(input()); assert request['method']=='account/usage/read'
print(json.dumps({'id':request['id'],'result':{'summary':{'lifetimeTokens':321,'secret':'hidden'},'dailyUsageBuckets':[{'startDate':'2026-09-24','tokens':12,'secret':'hidden'}]}}),flush=True)
''')
            result = await account.read_account([sys.executable, str(script)], timeout=2)
            self.assertEqual(result['windows'][0]['remaining'], 58)
            self.assertEqual(result['usage']['summary']['lifetimeTokens'], 321)
            self.assertEqual(result['usage']['dailyUsageBuckets'][0]['startDate'], '2026-09-24')
            self.assertNotIn('hidden', json.dumps(result))

    async def test_usage_error_does_not_clear_valid_quota(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / 'server.py'
            script.write_text('''import json
request=json.loads(input())
print(json.dumps({'id':request['id'],'result':{}}),flush=True)
input()
request=json.loads(input())
print(json.dumps({'id':request['id'],'result':{'rateLimits':{'primary':{'usedPercent':35}}}}),flush=True)
request=json.loads(input())
print(json.dumps({'id':request['id'],'error':{'code':-1}}),flush=True)
''')
            result = await account.read_account([sys.executable, str(script)], timeout=2)
            self.assertEqual(result['windows'][0]['remaining'], 65)
            self.assertNotIn('usage', result)

    async def test_timeout_and_missing(self):
        result = await account.read_account([sys.executable, '-c', 'import time; time.sleep(20)'], timeout=.1)
        self.assertEqual(result['errorCode'], 'timeout')
        result = await account.read_account(['/nonexistent/quota-v2-cli'], timeout=.1)
        self.assertEqual(result['errorCode'], 'cli_missing')

    async def test_overall_deadline_preserves_quota_when_optional_usage_stalls(self):
        from unittest.mock import AsyncMock, Mock, patch
        replies = iter([{'id': 1, 'result': {}}, {'id': 2, 'result': {
            'rateLimits': {'primary': {'usedPercent': 35}}}}])
        async def readline():
            reply = next(replies, None)
            if reply is None:
                await asyncio.Event().wait()
            return (json.dumps(reply) + '\n').encode()
        # Keep this deadline regression independent of OS process-start latency.
        # The real stdio handshake and process cleanup have separate integration tests.
        process = Mock(pid=123, returncode=0)
        process.stdin.drain = AsyncMock()
        process.stdout.readline = readline
        process.wait = AsyncMock(return_value=0)
        with patch.object(account.asyncio, 'create_subprocess_exec', AsyncMock(return_value=process)), \
                patch.object(account.os, 'killpg', create=True):
            result = await asyncio.wait_for(account.read_account(['/synthetic/cli'], timeout=.05), 2)
        self.assertEqual(result['status'], 'live')
        self.assertEqual(result['windows'][0]['remaining'], 65)
        self.assertNotIn('usage', result)

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
        client.evaluate.side_effect = ['one', False, False, False, True]
        loop.client = client
        with patch('quota_monitor.runtime.list_pages', return_value=[]), patch('quota_monitor.runtime.select_page', return_value=client.endpoint):
            self.assertEqual(await loop.step(), 'updated')
        expression = client.evaluate.call_args.args[0]
        self.assertIn('"quota": {"status": "live"', expression)
        loop.account.request_refresh()
        self.assertEqual(loop.account.next_read, 0)
        client.evaluate.side_effect = None
        client.evaluate.return_value = True
        await loop.shutdown()
        loop.account.close.assert_awaited_once()

    def test_project_preserves_bounded_usage_reset_credits_and_budget(self):
        result = account.project({'rateLimits': {'primary': {'usedPercent': 25}},
            'usage': {'dailyUsageBuckets': [{'tokens': 123, 'secret': 'drop'}],
                      'summary': {'lifetimeTokens': 456}},
            'resetCredits': {'availableCount': 2, 'nextExpiresAt': 2000, 'secret': 'drop'},
            'budget': {'kind': 'exhaust', 'seconds': 90, 'secret': 'drop'}}, now=1000)
        self.assertEqual(result['usage'], {'dailyUsageBuckets': [{'tokens': 123}],
                                           'summary': {'lifetimeTokens': 456}})
        self.assertEqual(result['resetCredits'], {'availableCount': 2, 'nextExpiresAt': 2000})
        self.assertEqual(result['budget'], {'kind': 'exhaust', 'seconds': 90})

    def test_current_reset_credit_field_uses_available_expiry(self):
        result = account.project({'rateLimits': {'primary': {'usedPercent': 25}},
            'rateLimitResetCredits': {'availableCount': 2, 'credits': [
                {'status': 'redeemed', 'expiresAt': 1000},
                {'status': 'available', 'expiresAt': 3000},
                {'status': 'available', 'expiresAt': 2000}]}}, now=1000)
        self.assertEqual(result['resetCredits'], {'availableCount': 2, 'nextExpiresAt': 2000})

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
