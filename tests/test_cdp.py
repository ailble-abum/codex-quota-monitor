import asyncio
import json
import unittest
import subprocess
import sys
from pathlib import Path

from websockets.asyncio.server import serve
from quota_monitor.cdp import CDPClient, CDPError


class CDPTests(unittest.IsolatedAsyncioTestCase):
    def test_probe_rejects_optimized_python(self):
        result = subprocess.run([sys.executable, '-O', 'tools/cdp_probe.py'],
                                cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('probe requires assertions enabled', result.stderr)

    async def server(self, handler, **options):
        server = await serve(handler, '127.0.0.1', 0, **options)
        self.addAsyncCleanup(server.wait_closed)
        self.addCleanup(server.close)
        return 'ws://127.0.0.1:%s/devtools/page/test' % server.sockets[0].getsockname()[1]

    async def test_events_and_ids_do_not_replace_result(self):
        async def handler(ws):
            for value in (3, 4):
                request = json.loads(await ws.recv())
                self.assertEqual(request['method'], 'Runtime.evaluate')
                self.assertTrue(request['params']['returnByValue'])
                await ws.send(json.dumps({'method': 'Runtime.consoleAPICalled', 'params': {}}))
                await ws.send(json.dumps({'id': request['id'] + 99, 'result': {}}))
                await ws.send(json.dumps({'id': request['id'], 'result': {'result': {'value': value}}}))
        url = await self.server(handler)
        async with CDPClient(url) as client:
            self.assertEqual(await client.evaluate('1+2'), 3)
            self.assertEqual(await client.evaluate('2+2'), 4)

    async def test_timeout_closes_connection_and_does_not_retry(self):
        requests = []
        async def handler(ws):
            requests.append(await ws.recv())
            await ws.wait_closed()
        url = await self.server(handler)
        async with CDPClient(url, timeout=0.05) as client:
            with self.assertRaisesRegex(CDPError, '^timeout$'):
                await client.evaluate('never resolves')
            with self.assertRaisesRegex(CDPError, '^disconnected$'):
                await client.evaluate('not resent')
        self.assertEqual(len(requests), 1)

    async def test_disconnect_is_generic(self):
        async def handler(ws):
            await ws.recv()
            await ws.close(reason='PRIVATE')
        async with CDPClient(await self.server(handler)) as client:
            with self.assertRaisesRegex(CDPError, '^disconnected$'):
                await client.evaluate('private expression')

    async def test_remote_and_javascript_errors_hide_details(self):
        for response, code in (({'error': {'message': 'PRIVATE'}}, 'remote_error'),
                               ({'result': {'exceptionDetails': {'text': 'PRIVATE'}}}, 'javascript_error')):
            async def handler(ws):
                request = json.loads(await ws.recv())
                await ws.send(json.dumps(dict(response, id=request['id'])))
            async with CDPClient(await self.server(handler)) as client:
                with self.assertRaisesRegex(CDPError, '^' + code + '$'):
                    await client.evaluate('throw Error("PRIVATE")')

    async def test_malformed_and_binary_responses_fail_closed(self):
        for raw in ('[]', 'bad json', b'{}', '{"id":true,"result":{}}'):
            async def handler(ws):
                await ws.recv()
                await ws.send(raw)
            async with CDPClient(await self.server(handler)) as client:
                with self.assertRaisesRegex(CDPError, '^protocol_error$'):
                    await client.evaluate('1')

    async def test_oversize_response_is_bounded(self):
        async def handler(ws):
            await ws.recv()
            await ws.send('x' * 8192)
        async with CDPClient(await self.server(handler), max_message=1024) as client:
            with self.assertRaisesRegex(CDPError, '^disconnected$'):
                await client.evaluate('1')

    async def test_cancel_closes_and_propagates(self):
        received = asyncio.Event()
        async def handler(ws):
            await ws.recv()
            received.set()
            await ws.wait_closed()
        async with CDPClient(await self.server(handler)) as client:
            task = asyncio.create_task(client.evaluate('wait'))
            await asyncio.wait_for(received.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            with self.assertRaisesRegex(CDPError, '^disconnected$'):
                await client.evaluate('1')

    async def test_redirect_is_not_followed(self):
        redirected = []
        async def target(ws):
            redirected.append(True)
        target_url = await self.server(target)
        def redirect(connection, request):
            response = connection.respond(302, 'redirect')
            response.headers['Location'] = target_url
            return response
        url = await self.server(target, process_request=redirect)
        with self.assertRaisesRegex(CDPError, '^unavailable$'):
            async with CDPClient(url):
                self.fail('redirect followed')
        self.assertEqual(redirected, [])

    async def test_event_flood_has_message_limit(self):
        async def handler(ws):
            await ws.recv()
            for _ in range(128):
                await ws.send('{"method":"event"}')
        async with CDPClient(await self.server(handler)) as client:
            with self.assertRaisesRegex(CDPError, '^message_limit$'):
                await client.evaluate('1')

    async def test_concurrent_evaluation_is_rejected(self):
        received, release = asyncio.Event(), asyncio.Event()
        async def handler(ws):
            request = json.loads(await ws.recv())
            received.set()
            await release.wait()
            await ws.send(json.dumps({'id': request['id'], 'result': {'result': {'value': 1}}}))
        async with CDPClient(await self.server(handler)) as client:
            task = asyncio.create_task(client.evaluate('first'))
            await asyncio.wait_for(received.wait(), 1)
            try:
                with self.assertRaisesRegex(CDPError, '^busy$'):
                    await client.evaluate('second')
            finally:
                release.set()
            self.assertEqual(await task, 1)

    async def test_oversize_request_is_not_sent(self):
        requests = []
        async def handler(ws):
            async for request in ws:
                requests.append(request)
        async with CDPClient(await self.server(handler), max_message=256) as client:
            with self.assertRaisesRegex(CDPError, '^request_too_large$'):
                await client.evaluate('x' * 300)
        self.assertEqual(requests, [])

    def test_invalid_endpoints_and_limits_rejected_before_connect(self):
        for url in ('ws://example.com:80/devtools/page/a', 'ws://127.0.0.1/devtools/page/a',
                    'ws://u:p@127.0.0.1:1/devtools/page/a', 'http://127.0.0.1:1/a',
                    'ws://127.0.0.1:1/devtools/page/a?secret=x', 'ws://127.0.0.1:1/other'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                CDPClient(url)
        for options in ({'timeout': 0}, {'timeout': float('nan')}, {'max_message': True}):
            with self.assertRaises(ValueError):
                CDPClient('ws://127.0.0.1:1/devtools/page/a', **options)
