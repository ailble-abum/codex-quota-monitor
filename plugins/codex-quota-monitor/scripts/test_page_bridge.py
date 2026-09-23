import unittest

import page_bridge


class PageBridgeTests(unittest.TestCase):
    def test_probe_reads_live_page_and_normalizes_non_object_results(self):
        class Client:
            def evaluate(self, expression):
                self.expression = expression
                return {"activeThreadId": "thread", "dom": {"sidebarRows": 2}}

        client = Client()
        self.assertEqual(page_bridge.read(client)["activeThreadId"], "thread")
        self.assertIn("data-app-action-sidebar-thread-row", client.expression)
        self.assertEqual(page_bridge.read(type("Empty", (), {"evaluate": lambda self, _: []})()), {})

    def test_host_bridge_keeps_renderer_selectors_and_refresh_outside_the_ui(self):
        script = page_bridge.HOST_BRIDGE_SCRIPT
        self.assertIn("function createPageBridge", script)
        self.assertIn("function createPageRefreshController", script)
        self.assertIn("data-content-search-assistant-turn-key", script)
        self.assertIn("new MutationObserver", script)
        self.assertIn("restoreSidebarRow", script)


if __name__ == "__main__":
    unittest.main()
