import asyncio
import json
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest.mock import AsyncMock, Mock, patch
from pathlib import Path
from quota_monitor import runtime


class SelectionTests(unittest.TestCase):
    def test_runtime_requires_explicit_supported_adapter_and_boolean_panel(self):
        for options in ({'host': 'guessed-dom'}, {'host': None}, {'panel': 'yes'}):
            with self.assertRaises(ValueError):
                runtime.UpdateLoop('http://127.0.0.1:9222', 'about:blank', {}, **options)

    def test_selection_is_exact_unique_and_local(self):
        page = {'type': 'page', 'id': 'one', 'url': 'http://fixture.invalid/',
                'webSocketDebuggerUrl': 'ws://127.0.0.1:9222/devtools/page/one'}
        self.assertEqual(runtime.select_page([page], page['url'], 'http://127.0.0.1:9222'),
                         page['webSocketDebuggerUrl'])
        for rows, code in (([], 'not_found'), ([page, page], 'ambiguous'),
                           ([dict(page, webSocketDebuggerUrl='ws://127.0.0.1:9223/devtools/page/one')], 'invalid_target')):
            with self.assertRaisesRegex(runtime.CDPError, '^' + code + '$'):
                runtime.select_page(rows, page['url'], 'http://127.0.0.1:9222')

    def test_existing_journal_is_read_incrementally_and_identity_checked(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'one.jsonl'
            path.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': 'one'}}) + '\n')
            source = runtime.JournalSource({'one': path})
            self.assertEqual(source.read('one')['selectedThreadId'], 'one')
            offset = source.journals['one'].reader._offset
            self.assertEqual(source.read('one')['selectedThreadId'], 'one')
            self.assertEqual(source.journals['one'].reader._offset, offset)
            self.assertEqual(source.read('missing')['summaries'], [])
            replacement = Path(root) / 'replacement'
            replacement.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': 'wrong'}}) + '\n')
            replacement.replace(path)
            self.assertEqual(source.read('one')['summaries'], [])


class LoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_history_uses_verified_active_summary_not_first_sidebar_row(self):
        loop = runtime.UpdateLoop('http://127.0.0.1:9222', 'about:blank', {})
        payload = {'selectedThreadId': 'active', 'summaries': [
            {'thread_id': 'other', 'model': 'wrong'},
            {'thread_id': 'active', 'model': 'right'}], 'health': {'count': 2}}
        loop.source.read = lambda _: payload.copy()
        loop.history = Mock()
        loop.history.record.return_value = {'samples': 1}
        client = AsyncMock()
        client.endpoint = 'ws://127.0.0.1:9222/devtools/page/one'
        client.evaluate.side_effect = ['active', True]
        loop.client = client
        with patch.object(runtime, 'list_pages', return_value=[]), \
                patch.object(runtime, 'select_page', return_value=client.endpoint):
            self.assertEqual(await loop.step(), 'updated')
        self.assertEqual(loop.history.record.call_args.args[1]['thread_id'], 'active')
        self.assertEqual(loop.history.record.call_args.args[3], 'right')
        payload['selectedThreadId'] = 'other'
        client.evaluate.side_effect = ['active', True]
        with patch.object(runtime, 'list_pages', return_value=[]), \
                patch.object(runtime, 'select_page', return_value=client.endpoint):
            self.assertEqual(await loop.step(), 'updated')
        self.assertEqual(loop.history.record.call_args.args[1:4], ({}, None, None))

    async def test_shutdown_after_initialization_without_publication(self):
        calls = []
        class Client:
            async def evaluate(self, expression):
                calls.append(expression)
                return True
            async def close(self):
                calls.append('closed')
        loop = runtime.UpdateLoop('http://127.0.0.1:9222', 'about:blank', {})
        loop.client = Client()
        loop._initialized = True
        self.assertEqual(await loop.shutdown(), 'released')
        self.assertIn('"action": "release"', calls[0])
        self.assertEqual(calls[-1], 'closed')
        self.assertFalse(loop._initialized)
        loop._initialized = True
        self.assertEqual(await loop.shutdown(), 'lease_pending')

    async def test_run_cancellation_closes_owned_connection(self):
        loop = runtime.UpdateLoop('http://127.0.0.1:9222', 'http://fixture.invalid/', {})
        started = asyncio.Event()
        closed = []
        async def step():
            started.set()
            await asyncio.Event().wait()
        async def close():
            closed.append(True)
        loop.step, loop.close = step, close
        task = asyncio.create_task(loop.run(interval=0.01))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(closed, [True])


class DiscoveryTests(unittest.TestCase):
    def test_http_list_and_redirect_rejection(self):
        state = {'status': 200, 'body': b'[]'}
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(state['status'])
                self.send_header('Content-Length', str(len(state['body'])))
                self.send_header('Location', 'http://example.invalid/private')
                self.end_headers()
                self.wfile.write(state['body'])
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            origin = 'http://127.0.0.1:%s' % server.server_port
            self.assertEqual(runtime.list_pages(origin), [])
            state['status'] = 302
            with self.assertRaisesRegex(runtime.CDPError, '^discovery_unavailable$'):
                runtime.list_pages(origin)
            state['status'], state['body'] = 200, b'{}'
            with self.assertRaisesRegex(runtime.CDPError, '^invalid_targets$'):
                runtime.list_pages(origin)
            state['body'] = b' ' * 1048577
            with self.assertRaisesRegex(runtime.CDPError, '^target_limit$'):
                runtime.list_pages(origin)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_discovery_rejects_nonlocal_and_credential_origins(self):
        for origin in ('http://localhost:9222', 'https://127.0.0.1:9222',
                       'http://127.0.0.1:9222/path', 'http://user@127.0.0.1:9222',
                       'http://192.168.1.1:9222', 'http://127.0.0.1:9222?secret'):
            with self.assertRaises(ValueError):
                runtime.local_origin(origin)


    def test_stalled_headers_end_within_request_budget(self):
        release = threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                release.wait(5)
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            start = time.monotonic()
            with self.assertRaisesRegex(runtime.CDPError, '^discovery_unavailable$'):
                runtime.list_pages('http://127.0.0.1:%s' % server.server_port)
            self.assertLess(time.monotonic() - start, 4)
        finally:
            release.set()
            server.shutdown()
            server.server_close()
            thread.join()
