import json
import tempfile
import unittest
from pathlib import Path

from context_token_inspector import (
    extend_session_detail,
    read_jsonl_from_offset,
    read_jsonl_reverse,
    summarize_session_fast,
)


class IndependentInspectorTests(unittest.TestCase):
    def test_reverse_reader_handles_chunk_boundaries_and_partial_tail(self):
        rows = [
            {"timestamp": "one", "type": "session_meta", "payload": {"id": "a"}},
            {"timestamp": "two", "type": "turn_context", "payload": {"model": "m"}},
            {"timestamp": "three", "type": "event_msg", "payload": {"type": "token_count", "info": {}}},
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "session.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\npartial", encoding="utf-8")
            self.assertEqual(
                [row.get("timestamp") for row in read_jsonl_reverse(path, chunk_size=9)],
                ["three", "two", "one"],
            )
            self.assertEqual(summarize_session_fast(path)["updated_at"], "three")

    def test_offset_reader_leaves_an_unfinished_line_for_next_pass(self):
        first = {"type": "session_meta", "payload": {"id": "a"}}
        second = {"type": "turn_context", "payload": {"model": "m"}}
        encoded = json.dumps(first) + "\n" + json.dumps(second)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "session.jsonl"
            path.write_text(encoded, encoding="utf-8")
            rows, offset = read_jsonl_from_offset(path, 0)
            self.assertEqual(rows, [first])
            self.assertEqual(offset, len(json.dumps(first).encode()) + 1)
            rows, next_offset = read_jsonl_from_offset(path, offset)
            self.assertEqual(rows, [])
            self.assertEqual(next_offset, offset)

    def test_incremental_detail_keeps_pending_assistant_until_token_count(self):
        detail = {"meta": {}, "messages": [], "_pending_assistant_index": None,
                  "_current_turn_index": 0}
        extend_session_detail(detail, [
            {"type": "response_item", "payload": {"type": "message", "role": "user", "content": "hi"}},
            {"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": "hello"}},
        ])
        self.assertEqual(detail["_pending_assistant_index"], 1)
        extend_session_detail(detail, [{
            "type": "event_msg", "payload": {"type": "token_count", "info": {
                "last_token_usage": {"input_tokens": 2}, "model_context_window": 4,
            }},
        }])
        self.assertIsNone(detail["_pending_assistant_index"])
        self.assertEqual(detail["messages"][1]["token_usage"]["latest_context_percent"], 50.0)


if __name__ == "__main__":
    unittest.main()
