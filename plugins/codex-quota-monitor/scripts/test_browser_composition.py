"""Optional real-browser coverage for the injected host bridge.

The normal unit suite stays dependency-free.  When Chrome is available, this
test uses its actual CDP endpoint instead of a DOM mock so selector drift,
MutationObserver scheduling, and a fresh CDP connection are exercised together.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from pathlib import Path
from typing import Any
from unittest import mock

from cdp_transport import CDPClient, CDPError, devtools_targets
import context_token_injector as injector
from context_token_injector import INJECTION_SCRIPT


PAGE = b"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Codex bridge fixture</title></head>
<body>
  <div data-app-action-sidebar-thread-row data-app-action-sidebar-thread-id="thread-a"
       data-app-action-sidebar-thread-active="true" title="Thread A">Thread A</div>
  <article data-content-search-assistant-turn-key id="answer-a">
    <p>Alpha assistant answer has enough unique words to match the local detail record.</p>
    <div><span data-assistant-message-sent-time>1:23 PM</span></div>
  </article>
</body></html>"""


class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - HTTP handler spelling
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(PAGE)))
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, _format: str, *_args: Any) -> None:
        pass


def chrome_binary() -> str | None:
    candidates = [
        os.environ.get("CTI_CHROME_BIN"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    return next((path for path in candidates if path and Path(path).is_file()), None)


def wait_for(condition, message: str, timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.05)
    raise AssertionError(message)


class BrowserCompositionTests(unittest.TestCase):
    """Use a local, temporary Chromium only when one is installed."""

    def setUp(self) -> None:
        binary = chrome_binary()
        if binary is None:
            self.skipTest("Chrome/Chromium is not installed")
        self.temporary = tempfile.TemporaryDirectory()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.profile = Path(self.temporary.name) / "profile"
        self.chrome = subprocess.Popen(
            [
                binary,
                "--headless=new",
                "--no-first-run",
                "--no-default-browser-check",
                "--remote-allow-origins=*",
                "--remote-debugging-port=0",
                f"--user-data-dir={self.profile}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        active_port = self.profile / "DevToolsActivePort"
        wait_for(active_port.is_file, "Chrome did not publish its DevTools port")
        self.port = int(active_port.read_text(encoding="utf-8").splitlines()[0])
        self.client = self.connect()
        self.client.call("Page.enable")
        self.client.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.server_port}/"})
        wait_for(lambda: self.client.evaluate("document.readyState") == "complete", "fixture did not load")

    def tearDown(self) -> None:
        client = getattr(self, "client", None)
        if client is not None:
            client.close()
        chrome = getattr(self, "chrome", None)
        if chrome is not None and chrome.poll() is None:
            chrome.terminate()
            try:
                chrome.wait(timeout=5)
            except subprocess.TimeoutExpired:
                chrome.kill()
                chrome.wait(timeout=5)
        server = getattr(self, "server", None)
        if server is not None:
            server.shutdown()
            server.server_close()
        thread = getattr(self, "server_thread", None)
        if thread is not None:
            thread.join(timeout=5)
        temporary = getattr(self, "temporary", None)
        if temporary is not None:
            temporary.cleanup()

    def connect(self) -> CDPClient:
        def page_target() -> dict[str, Any] | None:
            try:
                return next((target for target in devtools_targets(self.port)
                             if target.get("type") == "page" and target.get("webSocketDebuggerUrl")), None)
            except CDPError:
                return None

        target: dict[str, Any] | None = None
        wait_for(lambda: bool(page_target()), "Chrome did not expose a page target")
        target = page_target()
        if target is None:
            raise AssertionError("missing page target")
        return CDPClient(str(target["webSocketDebuggerUrl"]), timeout=3)

    def payload(self, thread_id: str, prefix: str) -> dict[str, Any]:
        context_tokens = 101 if thread_id == "thread-a" else 202
        detail = {
            "thread_id": thread_id,
            "assistantItems": [{
                "footer": f"{thread_id} footer",
                "chip": f"{thread_id} chip",
                "textPrefix": prefix,
                "roundIndex": 1,
                "totalRounds": 1,
                "assistantTurnIndex": 1,
                "assistantTotalTurns": 1,
                "tokenUsage": {
                    "latest_context_tokens": context_tokens,
                    "context_window": 1000,
                    "latest_context_percent": context_tokens / 10,
                    "latest_turn_total_tokens": 30,
                    "session_total_tokens": 300,
                    "latest_turn_input_tokens": 20,
                    "latest_turn_output_tokens": 10,
                    "latest_turn_reasoning_tokens": 0,
                },
            }],
        }
        return {
            "activeThreadId": thread_id,
            "selectedThreadId": thread_id,
            "summaries": [{
                "thread_id": thread_id,
                "thread_keys": [thread_id, f"local:{thread_id}"],
                "hover": f"{thread_id} hover",
            }],
            "detail": detail,
            "detailsByThread": {thread_id: detail, f"local:{thread_id}": detail},
            "quota": {"status": "unavailable", "windows": []},
            "health": None,
            "build": {},
            "update": {},
            "dom": {},
            "observedAt": time.time(),
        }

    def evaluate_injected(self, payload: dict[str, Any]) -> Any:
        return self.client.evaluate(f"({INJECTION_SCRIPT})({json.dumps(payload)})")

    def test_host_bridge_composes_with_the_custom_overlay_and_reconnects(self) -> None:
        alpha = "Alpha assistant answer has enough unique words to match the local detail record."
        result = self.evaluate_injected(self.payload("thread-a", alpha))
        self.assertTrue(result["ok"])
        wait_for(
            lambda: "Current 101" in (self.client.evaluate("document.querySelector('[data-context-token-chip]')?.textContent") or ""),
            "initial detail chip did not render",
        )
        state = self.client.evaluate("""(() => ({
          root: Boolean(document.getElementById('codex-context-token-inspector-root')),
          hover: document.querySelector('[data-app-action-sidebar-thread-row]').getAttribute('data-context-token-sidebar-hover'),
          chip: document.querySelector('[data-context-token-chip]')?.textContent,
          tabStop: document.querySelector('[data-app-action-sidebar-thread-row]').hasAttribute('tabindex')
        }))()""")
        self.assertTrue(state["root"])
        self.assertIn("Session total", state["hover"])
        self.assertIn("Current 101", state["chip"])
        self.assertTrue(state["tabStop"])

        beta = "Beta assistant answer has enough unique words to exercise visible page matching."
        self.client.evaluate("""(() => {
          const alpha = document.querySelector('[data-app-action-sidebar-thread-row]');
          alpha.setAttribute('data-app-action-sidebar-thread-active', 'false');
          const beta = document.createElement('div');
          beta.setAttribute('data-app-action-sidebar-thread-row', '');
          beta.setAttribute('data-app-action-sidebar-thread-id', 'thread-b');
          beta.setAttribute('data-app-action-sidebar-thread-active', 'true');
          beta.setAttribute('title', 'Thread B');
          beta.textContent = 'Thread B';
          document.body.appendChild(beta);
          const answer = document.createElement('article');
          answer.setAttribute('data-content-search-assistant-turn-key', '');
          answer.innerHTML = '<p>Beta assistant answer has enough unique words to exercise visible page matching.</p><div><span data-assistant-message-sent-time>1:24 PM</span></div>';
          document.body.appendChild(answer);
        })()""")
        wait_for(
            lambda: self.client.evaluate("window.__codexContextTokenInspectorPayload.activeThreadId") == "thread-b",
            "MutationObserver did not refresh the active task",
        )
        matched = self.client.evaluate("""(() => window.__codexContextTokenInspectorPageBridge
          .detailForVisiblePage({detailsByThread: {b: {
            thread_id: 'thread-b', assistantItems: [{textPrefix: 'Beta assistant answer has enough unique words to exercise visible page matching.'}]
          }}})?.thread_id)()""")
        self.assertEqual(matched, "thread-b")

        self.client.evaluate(
            f"window.__codexContextTokenInspectorUpdate({json.dumps(self.payload('thread-b', beta))})"
        )
        wait_for(
            lambda: "Current 202" in (self.client.evaluate("document.querySelector('[data-context-token-chip]')?.textContent") or ""),
            "data-only update did not refresh the detail chip",
        )
        decorated_beta = self.client.evaluate("""(() => {
          const row = document.querySelector('[data-app-action-sidebar-thread-id="thread-b"]');
          return {title: row.getAttribute('title'), hover: row.getAttribute('data-context-token-sidebar-hover'), tabStop: row.hasAttribute('tabindex')};
        })()""")
        self.assertEqual(decorated_beta["title"], None)
        self.assertTrue(decorated_beta["hover"])
        self.assertTrue(decorated_beta["tabStop"])

        # A fresh CDP socket to the same Chromium target proves the transport
        # can resume delivery after a renderer-side connection goes away.
        self.client.close()
        self.client = self.connect()
        self.client.evaluate(
            f"window.__codexContextTokenInspectorUpdate({json.dumps(self.payload('thread-b', beta))})"
        )
        self.assertIn(
            "Current 202",
            self.client.evaluate("document.querySelector('[data-context-token-chip]')?.textContent") or "",
        )

        self.client.evaluate("""(() => document.querySelector('[data-app-action-sidebar-thread-id="thread-b"]')
          .dispatchEvent(new FocusEvent('focusin', {bubbles: true})))()""")
        wait_for(
            lambda: self.client.evaluate("Boolean(document.querySelector('.cti-sidebar-tooltip'))"),
            "sidebar tooltip did not open",
        )
        restored = self.client.evaluate("""(() => {
          window.__codexContextTokenInspectorHideSidebarTooltip();
          window.__codexContextTokenInspectorPageRefresh.dispose();
          window.__codexContextTokenInspectorPageBridge.clearSidebar();
          const row = document.querySelector('[data-app-action-sidebar-thread-id="thread-b"]');
          return {title: row.getAttribute('title'), hover: row.getAttribute('data-context-token-sidebar-hover'), tabStop: row.hasAttribute('tabindex'), tooltip: Boolean(document.querySelector('.cti-sidebar-tooltip'))};
        })()""")
        self.assertEqual(restored, {"title": "Thread B", "hover": None, "tabStop": False, "tooltip": False})

        # Native virtualization can update a retained row while the overlay is
        # installed. Re-inject, emulate that update, and verify cleanup does
        # not revive the older decoration snapshot.
        self.evaluate_injected(self.payload("thread-b", beta))
        preserved = self.client.evaluate("""(() => {
          const row = document.querySelector('[data-app-action-sidebar-thread-id="thread-b"]');
          row.setAttribute('title', 'Renamed Thread B');
          row.setAttribute('tabindex', '-1');
          window.__codexContextTokenInspectorPageBridge.clearSidebar();
          return {title: row.getAttribute('title'), hover: row.getAttribute('data-context-token-sidebar-hover'), tabindex: row.getAttribute('tabindex')};
        })()""")
        self.assertEqual(preserved, {"title": "Renamed Thread B", "hover": None, "tabindex": "-1"})

    def test_injector_reconnects_to_a_real_cdp_endpoint(self) -> None:
        class StopRun(RuntimeError):
            pass

        calls: list[CDPClient] = []

        def real_page_target(targets: list[dict[str, Any]]) -> dict[str, Any]:
            return next(target for target in targets if target.get("type") == "page")

        def inject_then_drop(client: CDPClient, *_args: Any) -> dict[str, bool]:
            calls.append(client)
            if len(calls) == 1:
                client.evaluate("window.__ctiReconnectProbe = 1")
                client.close()
                return {"first": True}
            if len(calls) == 2:
                # This is a real socket failure, not a mocked CDP exception.
                client.evaluate("window.__ctiReconnectProbe = 2")
            client.evaluate("window.__ctiReconnectProbe = 3")
            raise StopRun()

        with mock.patch.object(injector, "select_target", side_effect=real_page_target), \
             mock.patch.object(injector, "inject_once", side_effect=inject_then_drop), \
             mock.patch.object(injector.time, "sleep"):
            with redirect_stderr(StringIO()), self.assertRaises(StopRun):
                injector.main(["--port", str(self.port), "--interval", "0.01", "--quiet"])

        self.assertEqual(len(calls), 3)
        self.assertIsNot(calls[0], calls[-1])
        self.assertEqual(self.client.evaluate("window.__ctiReconnectProbe"), 3)


if __name__ == "__main__":
    unittest.main()
