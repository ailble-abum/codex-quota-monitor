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


if __name__ == "__main__":
    unittest.main()
