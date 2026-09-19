import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'private-name.jsonl'

    def run_preview(self, *extra):
        return subprocess.run([sys.executable, '-m', 'quota_monitor', str(self.path),
                               '--thread', 'demo', *extra], capture_output=True,
                              text=True, timeout=10,
                              cwd=Path(__file__).resolve().parents[1])

    def test_complete_file_reaches_legacy_numeric_field(self):
        rows = [{'type': 'session_meta', 'payload': {'id': 'demo'}},
                {'type': 'response_item', 'payload': {'text': 'SECRET'}},
                {'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {
                    'total_token_usage': {'total_tokens': 90},
                    'last_token_usage': {'input_tokens': 20}, 'model_context_window': 100}}}]
        self.path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        result = self.run_preview()
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value['payload']['summaries'][0]['latest_context_percent'], 20)
        self.assertNotIn('SECRET', result.stdout)
        self.assertNotIn(str(self.path), result.stdout)

    def test_missing_file_reports_failure_without_path(self):
        result = self.run_preview()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['status'], 'unavailable')
        self.assertNotIn(str(self.path), result.stdout + result.stderr)

    def test_budget_exhaustion_does_not_publish_partial_summary(self):
        self.path.write_bytes(b'{}\n' * 100000)
        result = self.run_preview('--max-polls', '1')
        self.assertEqual(result.returncode, 2)
        value = json.loads(result.stdout)
        self.assertEqual(value['status'], 'incomplete')
        self.assertEqual(value['payload']['summaries'], [])

    def test_invalid_budget_rejected(self):
        self.assertEqual(self.run_preview('--max-polls', '0').returncode, 2)

    def test_unverified_identity_never_publishes(self):
        for expected, rows in (
                ('identity_missing', []),
                ('identity_mismatch', [{'type': 'session_meta', 'payload': {'id': 'other'}}]),
                ('identity_conflict', [{'type': 'session_meta', 'payload': {'id': 'demo'}},
                                      {'type': 'session_meta', 'payload': {'id': 'other'}}])):
            with self.subTest(rows=rows):
                self.path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
                result = self.run_preview()
                self.assertEqual(result.returncode, 2)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], expected)
                self.assertEqual(value['payload']['summaries'], [])
                self.assertNotIn('other', result.stdout)


if __name__ == '__main__':
    unittest.main()
