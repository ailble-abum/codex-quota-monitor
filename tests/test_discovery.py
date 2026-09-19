import json
import os
import tempfile
import unittest
from pathlib import Path

from quota_monitor import discovery


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def journal(self, name, identity='demo'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [{'type': 'session_meta', 'payload': {'id': identity}},
                {'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {
                    'total_token_usage': {'total_tokens': 123}}}}]
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        return path

    def test_nested_metadata_match_not_filename(self):
        self.journal('2026/09/20/unrelated-name.jsonl')
        self.journal('demo.jsonl', 'other')
        result = discovery.discover(self.root, 'local:demo')
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['reading']['thread_id'], 'demo')
        self.assertEqual(result['reading']['session']['total']['total_tokens'], 123)
        self.assertNotIn(str(self.root), repr(result))

    def test_duplicate_never_picks_newest(self):
        self.journal('one.jsonl')
        self.journal('two.jsonl')
        result = discovery.discover(self.root, 'demo')
        self.assertEqual(result['status'], 'ambiguous')
        self.assertIsNone(result['reading'])

    def test_no_match(self):
        self.journal('demo.jsonl', 'other')
        self.assertEqual(discovery.discover(self.root, 'demo')['status'], 'not_found')

    def test_unreadable_root(self):
        self.assertEqual(discovery.discover(self.root / 'absent', 'demo')['status'], 'unavailable')

    def test_total_byte_budget_blocks_partial_result(self):
        path = self.journal('one.jsonl')
        result = discovery.discover(self.root, 'demo', max_bytes=path.stat().st_size - 1)
        self.assertEqual(result['status'], 'incomplete')
        self.assertIsNone(result['reading'])
        self.assertLessEqual(result['bytes_read'], path.stat().st_size - 1)

    def test_exact_byte_budget_can_complete(self):
        path = self.journal('one.jsonl')
        self.assertEqual(discovery.discover(self.root, 'demo',
                         max_bytes=path.stat().st_size)['status'], 'ok')

    def test_entry_budget_includes_non_journals(self):
        for number in range(3):
            (self.root / str(number)).touch()
        result = discovery.discover(self.root, 'demo', max_entries=2)
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['entries'], 2)

    def test_depth_budget_is_not_a_false_not_found(self):
        self.journal('nested/one.jsonl')
        self.assertEqual(discovery.discover(self.root, 'demo', max_depth=0)['status'], 'incomplete')

    def test_unknown_or_conflicting_file_blocks_unique_claim(self):
        self.journal('one.jsonl')
        uncertain = self.root / 'uncertain.jsonl'
        for text in ('{}\n', '{broken}\n',
                     '{"type":"session_meta","payload":{"id":"other"}}\n'
                     '{"type":"session_meta","payload":{"id":"demo"}}\n'):
            with self.subTest(text=text):
                uncertain.write_text(text)
                result = discovery.discover(self.root, 'demo')
                self.assertEqual(result['status'], 'incomplete')
                self.assertIsNone(result['reading'])

    def test_symlinks_and_special_files_are_out_of_scope(self):
        self.journal('one.jsonl')
        (self.root / 'alias.jsonl').symlink_to(self.root / 'one.jsonl')
        (self.root / 'loop').symlink_to(self.root, target_is_directory=True)
        if hasattr(os, 'mkfifo'):
            os.mkfifo(self.root / 'pipe.jsonl')
        result = discovery.discover(self.root, 'demo')
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['files'], 1)

    def test_root_symlink_rejected(self):
        (self.root / 'alias').symlink_to(self.root, target_is_directory=True)
        self.assertEqual(discovery.discover(self.root / 'alias', 'demo')['status'], 'unavailable')

    def test_unterminated_tail_is_incomplete(self):
        path = self.journal('one.jsonl')
        with path.open('a') as stream:
            stream.write('{"type":"session_meta"')
        self.assertEqual(discovery.discover(self.root, 'demo')['status'], 'incomplete')

    def test_invalid_arguments(self):
        for options in ({'max_entries': 0}, {'max_bytes': 0}, {'max_depth': -1},
                        {'max_depth': 1000}, {'max_entries': True}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                discovery.discover(self.root, 'demo', **options)
        with self.assertRaises(ValueError):
            discovery.discover(self.root, '../demo')
