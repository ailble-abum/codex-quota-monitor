import json
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent


class LauncherScriptTests(unittest.TestCase):
    def test_shell_entrypoints_parse_and_validate_ports(self):
        for name in ("port_utils.sh", "reopen_codex_with_debug.sh", "start_codex_monitor.sh"):
            with self.subTest(name=name):
                result = subprocess.run(["bash", "-n", str(SCRIPTS / name)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
        probe = (
            f"source {SCRIPTS / 'port_utils.sh'}; "
            "codex_monitor_valid_port 9222 && "
            "! codex_monitor_valid_port 0 && "
            "! codex_monitor_valid_port 65536"
        )
        self.assertEqual(subprocess.run(["bash", "-c", probe]).returncode, 0)

    def test_install_launcher_allows_debug_port_recovery(self):
        monitorctl = (SCRIPTS / "monitorctl.py").read_text(encoding="utf-8")
        start = (SCRIPTS / "start_codex_monitor.sh").read_text(encoding="utf-8")
        self.assertIn("'9222'], 'RunAtLoad'", monitorctl)
        self.assertNotIn("'9222', '--no-reopen-after-quit'", monitorctl)
        self.assertIn('reopen_codex_with_debug.sh', start)
        self.assertIn('CODEX_MONITOR_REOPEN_AFTER_QUIT', start)
        self.assertIn('codex_monitor_wait_for_devtools', start)

    def test_launcher_uses_the_shared_cdp_target_classifier(self):
        source = (SCRIPTS / "port_utils.sh").read_text(encoding="utf-8")
        self.assertIn('cdp_transport.py" target-state', source)
        self.assertNotIn("urllib.request.urlopen", source)

    def test_shell_probe_calls_the_shared_transport_for_owned_and_ready_state(self):
        class Handler(BaseHTTPRequestHandler):
            targets = []

            def do_GET(self):
                body = json.dumps(self.targets).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            Handler.targets = [{"type": "page", "title": "Codex", "url": "app://-/index.html?initialRoute=home"}]
            probe = f"source {SCRIPTS / 'port_utils.sh'}; codex_monitor_devtools_owned {server.server_port} && ! codex_monitor_devtools_ready {server.server_port}"
            result = subprocess.run(["bash", "-c", probe], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)

            Handler.targets = [{"type": "page", "title": "Codex", "url": "app://-/index.html"}]
            probe = f"source {SCRIPTS / 'port_utils.sh'}; codex_monitor_devtools_ready {server.server_port}"
            result = subprocess.run(["bash", "-c", probe], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
