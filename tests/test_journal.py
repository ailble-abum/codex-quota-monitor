import json
import tempfile
import unittest
from pathlib import Path

from quota_monitor.journal import SessionJournal


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'synthetic.jsonl'
        self.journal = SessionJournal(self.path, read_budget=64)

    def write(self, rows, mode='w'):
        with self.path.open(mode, encoding='utf-8') as stream:
            for row in rows:
                stream.write(json.dumps(row) + '\n')

    def drain(self):
        for _ in range(100):
            result = self.journal.poll()
            if not result['more']:
                return result
        self.fail('not drained')

    def test_append_projects_only_usage_and_model_fields(self):
        self.write([{'type': 'turn_context', 'payload': {'model': 'demo', 'effort': 'high', 'cwd': '/private/project'}},
                    {'type': 'response_item', 'payload': {'text': 'secret-body'}}])
        result = self.drain()
        self.assertEqual(result['session']['model'], 'demo')
        self.assertNotIn('secret-body', json.dumps(result))
        self.assertNotIn('/private/project', json.dumps(result))
        self.write([{'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {
            'total_token_usage': {'total_tokens': 123},
            'last_token_usage': {'input_tokens': 50}, 'model_context_window': 100}}}], 'a')
        self.assertEqual(self.drain()['session']['context_percent'], 50)
        self.assertEqual(self.journal.poll()['bytes_read'], 0)

    def test_replacement_resets_old_model_and_usage(self):
        self.write([{'type': 'turn_context', 'payload': {'model': 'old'}}])
        self.drain()
        replacement = self.path.with_suffix('.new')
        replacement.write_text('{}\n')
        replacement.replace(self.path)
        result = self.journal.poll()
        self.assertTrue(result['reset'])
        self.assertIsNone(result['session']['model'])

    def test_unavailable_is_explicit_with_last_known_state(self):
        self.write([{'type': 'turn_context', 'payload': {'model': 'old'}}])
        self.drain()
        self.path.rename(self.path.with_suffix('.parked'))
        result = self.journal.poll()
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['session']['model'], 'old')


if __name__ == '__main__':
    unittest.main()
