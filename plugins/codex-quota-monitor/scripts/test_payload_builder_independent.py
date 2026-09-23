import json
import tempfile
import unittest
from pathlib import Path

import payload_builder


class IndependentPayloadTests(unittest.TestCase):
    def test_only_selected_thread_gets_message_details(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for thread in ("one", "two"):
                (root / f"{thread}.jsonl").write_text("\n".join([
                    json.dumps({"type": "session_meta", "payload": {"id": thread}}),
                    json.dumps({"type": "response_item", "payload": {
                        "type": "message", "role": "assistant", "content": "answer",
                    }}),
                    json.dumps({"type": "event_msg", "payload": {"type": "token_count", "info": {
                        "last_token_usage": {"input_tokens": 2, "total_tokens": 3},
                        "total_token_usage": {"total_tokens": 3}, "model_context_window": 4,
                    }}}),
                ]))
            payload = payload_builder.build_payload([folder], 10, "two")
            self.assertEqual(set(payload["detailsByThread"]), {"two", "local:two"})
            self.assertNotIn("one", payload["detailsByThread"])

    def test_cache_appends_complete_rows_after_an_incomplete_write(self):
        payload_builder._DETAIL_CACHE.clear()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "thread.jsonl"
            path.write_text(json.dumps({"type": "session_meta", "payload": {"id": "thread"}}) + "\n")
            summary = {"path": str(path), "thread_id": "thread"}
            parsed = payload_builder.cached_session_detail(str(path), summary)
            with path.open("a") as handle:
                handle.write(json.dumps({"type": "response_item", "payload": {
                    "type": "message", "role": "assistant", "content": "ok",
                }}))
            self.assertEqual(len(payload_builder.cached_session_detail(str(path), summary)["messages"]), 0)
            with path.open("a") as handle:
                handle.write("\n")
            self.assertIs(parsed, payload_builder.cached_session_detail(str(path), summary))
            self.assertEqual(len(parsed["messages"]), 1)


if __name__ == "__main__":
    unittest.main()
