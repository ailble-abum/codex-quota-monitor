import json
import os
import signal
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class LiveCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name) / 'PRIVATE-config.json'
        self.reserved = socket.socket()
        self.reserved.bind(('127.0.0.1', 0))
        self.addCleanup(self.reserved.close)
        self.origin = 'http://127.0.0.1:%s' % self.reserved.getsockname()[1]
        self.value = {'origin': self.origin, 'page_url': 'about:blank',
                      'journals': {'one': 'one.jsonl'}}

    def run_cli(self, *extra):
        self.config.write_text(json.dumps(self.value))
        return subprocess.run([sys.executable, '-m', 'quota_monitor.live',
            '--config', str(self.config), *extra], capture_output=True, text=True, timeout=10)

    def test_help_does_not_require_optional_dependency(self):
        result = subprocess.run([sys.executable, '-S', '-m', 'quota_monitor.live', '--help'],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--once', result.stdout)

    def test_once_reports_failure_without_endpoint_or_paths(self):
        result = self.run_cli('--once')
        self.assertEqual(result.returncode, 2)
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(rows[0], {'event': 'state', 'status': 'discovery_unavailable'})
        self.assertEqual(rows[-1]['reason'], 'once')
        self.assertNotIn('127.0.0.1', result.stdout + result.stderr)
        self.assertNotIn('PRIVATE', result.stdout + result.stderr)

    def test_failure_limit_and_unchanged_status_is_not_repeated(self):
        result = self.run_cli('--interval', '0.1', '--max-failures', '2')
        self.assertEqual(result.returncode, 2, result.stderr)
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(sum(row['event'] == 'state' for row in rows), 1)
        self.assertEqual(rows[-1]['reason'], 'failure_limit')

    def test_invalid_config_is_rejected_without_echoing_contents(self):
        for edit in ({'origin': 'http://PRIVATE.invalid:22'}, {'unknown': 'PRIVATE'},
                     {'journals': {'local:one': 'PRIVATE'}}, {'panel': 'PRIVATE'},
                     {'host': 'PRIVATE'}, {'journals': []}):
            with self.subTest(edit=edit):
                self.value.update(edit)
                result = self.run_cli('--once')
                self.assertEqual(result.returncode, 2)
                self.assertIn('invalid_config', result.stderr)
                self.assertNotIn('PRIVATE', result.stdout + result.stderr)
                self.value = {'origin': self.origin, 'page_url': 'about:blank',
                              'journals': {'one': 'one.jsonl'}}

    def test_directory_source_config_is_explicit_and_exclusive(self):
        from quota_monitor.live import load_config
        self.value.pop('journals')
        self.value['session_root'] = 'sessions'
        self.config.write_text(json.dumps(self.value))
        self.assertEqual(load_config(self.config)['session_root'], self.config.parent / 'sessions')
        for root in ('', None, 123, 'bad\0root'):
            self.value['session_root'] = root
            self.config.write_text(json.dumps(self.value))
            with self.assertRaises(ValueError):
                load_config(self.config)
        self.value.update(session_root='sessions', journals={'one': 'one.jsonl'})
        self.config.write_text(json.dumps(self.value))
        with self.assertRaises(ValueError):
            load_config(self.config)

    def test_consumer_requires_panel_and_valid_pinned_file(self):
        import hashlib
        from quota_monitor.live import load_config
        source = b'(empty => {})'
        script = self.config.parent / 'consumer.js'
        script.write_bytes(source)
        self.value['consumer'] = {'path': 'consumer.js', 'sha256': hashlib.sha256(source).hexdigest()}
        self.config.write_text(json.dumps(self.value))
        self.assertEqual(load_config(self.config)['consumer']['path'], script)
        result = self.run_cli('--once')
        self.assertIn('invalid_config', result.stderr)
        self.value['panel'] = True
        self.value['consumer']['sha256'] = '0' * 64
        result = self.run_cli('--once')
        self.assertIn('invalid_config', result.stderr)
        self.assertNotIn('PRIVATE', result.stderr)
        for consumer in (None, {}, {'path': 3, 'sha256': '0' * 64}):
            self.value['consumer'] = consumer
            result = self.run_cli('--once')
            self.assertIn('invalid_config', result.stderr)

    def test_duplicate_config_keys_are_rejected(self):
        self.config.write_text('{"origin":"PRIVATE", "origin":"other"}')
        result = subprocess.run([sys.executable, '-m', 'quota_monitor.live', '--config', str(self.config)],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn('invalid_config', result.stderr)
        self.assertNotIn('PRIVATE', result.stderr)

    @unittest.skipIf(os.name == 'nt', 'POSIX subprocess signal acceptance')
    def test_sigterm_exits_without_traceback(self):
        self.config.write_text(json.dumps(self.value))
        proc = subprocess.Popen([sys.executable, '-m', 'quota_monitor.live', '--config', str(self.config),
                                 '--interval', '60'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            import select
            ready, _, _ = select.select([proc.stdout], [], [], 5)
            self.assertTrue(ready, 'process did not report readiness')
            self.assertEqual(json.loads(proc.stdout.readline())['event'], 'state')
            proc.send_signal(signal.SIGTERM)
            out, err = proc.communicate(timeout=6)
            self.assertEqual(proc.returncode, 143, err)
            self.assertEqual(json.loads(out.strip())['reason'], 'sigterm')
            self.assertEqual(err, '')
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            proc.stdout.close()
            proc.stderr.close()


    def test_failure_retry_uses_backoff_and_stops_at_exact_budget(self):
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append(time.monotonic())
                self.send_response(200)
                self.send_header('Content-Length', '2')
                self.end_headers()
                self.wfile.write(b'[]')
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.value['origin'] = 'http://127.0.0.1:%s' % server.server_port
            result = self.run_cli('--interval', '0.1', '--max-failures', '3')
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(len(calls), 3)
            self.assertGreaterEqual(calls[1] - calls[0], 0.08)
            self.assertGreaterEqual(calls[2] - calls[1], 0.18)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_optional_dependency_failure_and_argument_errors_hide_values(self):
        self.config.write_text(json.dumps(self.value))
        result = subprocess.run([sys.executable, '-S', '-m', 'quota_monitor.live',
                                 '--config', str(self.config)], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn('dependency_unavailable', result.stderr)
        for options in (['--PRIVATE'], ['--interval', 'nan'], ['--max-failures', '0']):
            result = self.run_cli(*options)
            self.assertEqual(result.returncode, 2)
            self.assertIn('invalid_arguments', result.stderr)
            self.assertNotIn('PRIVATE', result.stderr)


    @unittest.skipIf(os.name == 'nt', 'POSIX signal while waiting for a missing host')
    def test_wait_mode_keeps_cli_alive_and_sigterm_cancels_sleep(self):
        import select
        self.config.write_text(json.dumps(self.value))
        proc = subprocess.Popen([sys.executable, '-m', 'quota_monitor.live', '--config', str(self.config),
            '--wait-for-host', '--max-failures', '1'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ready, _, _ = select.select([proc.stdout], [], [], 5)
            self.assertTrue(ready)
            self.assertEqual(json.loads(proc.stdout.readline())['status'], 'discovery_unavailable')
            time.sleep(.2)
            self.assertIsNone(proc.poll())
            proc.send_signal(signal.SIGTERM)
            out, err = proc.communicate(timeout=3)
            self.assertEqual(proc.returncode, 143, err)
            self.assertEqual(json.loads(out.strip())['reason'], 'sigterm')
            self.assertEqual(err, '')
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            proc.stdout.close()
            proc.stderr.close()

    def test_wait_flag_does_not_change_once(self):
        result = self.run_cli('--once', '--wait-for-host')
        self.assertEqual(result.returncode, 2)
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(rows[-1]['reason'], 'once')
        self.assertEqual(rows[0]['status'], 'discovery_unavailable')


class SupervisorTests(unittest.IsolatedAsyncioTestCase):
    async def test_unexpected_cleanup_error_is_sanitized_and_handlers_restored(self):
        import contextlib
        import io
        from quota_monitor.live import supervise
        class BrokenLoop:
            async def step(self):
                raise RuntimeError('PRIVATE runtime error')
            async def shutdown(self):
                raise RuntimeError('PRIVATE cleanup error')
        handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = await supervise(BrokenLoop(), interval=1, max_failures=1, once=False)
        self.assertEqual(code, 3)
        self.assertNotIn('PRIVATE', out.getvalue() + err.getvalue())
        self.assertEqual(json.loads(out.getvalue())['cleanup'], 'cleanup_failed')
        self.assertEqual(handlers, {sig: signal.getsignal(sig) for sig in handlers})

    @unittest.skipIf(os.name == 'nt', 'POSIX signal delivery during cleanup')
    async def test_signal_at_once_boundary_does_not_cancel_cleanup(self):
        import asyncio
        import contextlib
        import io
        from quota_monitor.live import supervise
        for phase in ('step', 'shutdown'):
            class Loop:
                async def step(self):
                    if phase == 'step':
                        os.kill(os.getpid(), signal.SIGTERM)
                    return 'updated'
                async def shutdown(self):
                    if phase == 'shutdown':
                        os.kill(os.getpid(), signal.SIGTERM)
                    await asyncio.sleep(0.01)
                    return 'released'
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = await supervise(Loop(), interval=1, max_failures=1, once=True)
            self.assertEqual(code, 143)
            self.assertEqual(json.loads(out.getvalue().splitlines()[-1]),
                             {'event': 'stopped', 'reason': 'sigterm', 'cleanup': 'released'})

    async def test_wait_mode_survives_missing_host_then_resumes_and_bounds_other_errors(self):
        import asyncio
        import contextlib
        import io
        from unittest.mock import patch, AsyncMock
        from quota_monitor.live import supervise
        class Loop:
            def __init__(self):
                self.values = iter(['discovery_unavailable'] * 6 + ['not_found', 'updated', 'ambiguous', 'ambiguous'])
                self.closed = False
            async def step(self):
                return next(self.values)
            async def shutdown(self):
                self.closed = True
                return 'closed'
        loop = Loop()
        out = io.StringIO()
        with contextlib.redirect_stdout(out), patch.object(asyncio, 'sleep', new_callable=AsyncMock) as sleep:
            code = await supervise(loop, interval=.1, max_failures=2, once=False, wait_for_host=True)
        self.assertEqual(code, 2)
        self.assertTrue(loop.closed)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [15] * 7 + [.1, .1])
        rows = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual([row['status'] for row in rows if row['event'] == 'state'],
                         ['discovery_unavailable', 'not_found', 'updated', 'ambiguous'])
        self.assertEqual(rows[-1]['reason'], 'failure_limit')
