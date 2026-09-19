import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from quota_monitor import indexed


@unittest.skipUnless(hasattr(os, 'O_NOFOLLOW') and os.open in os.supports_dir_fd,
                     'requires descriptor-relative safe directory access')
class IndexedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def journal(self, name, key='one', count=10):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(json.dumps(row) + '\n' for row in [
            {'type': 'session_meta', 'payload': {'id': key}},
            {'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {
                'last_token_usage': {'input_tokens': count}, 'model_context_window': 100}}}]))
        return path

    def test_metadata_association_append_and_no_rescan_when_unchanged(self):
        path = self.journal('nested/unrelated-name.jsonl')
        source = indexed.DirectorySource(self.root)
        self.assertEqual(source.read('one')['selectedThreadId'], 'one')
        with patch('os.scandir', side_effect=AssertionError('must not rescan')):
            self.assertEqual(source.read('one')['selectedThreadId'], 'one')
            self.assertEqual(source.bytes_read, 0)
            with path.open('a') as stream:
                stream.write(json.dumps({'type': 'event_msg', 'payload': {'type': 'token_count',
                    'info': {'last_token_usage': {'input_tokens': 20}}}}) + '\n')
            self.assertEqual(source.read('one')['summaries'][0]['latest_context_tokens'], 20)
            self.assertLess(source.bytes_read, path.stat().st_size)

    def test_inventory_change_clears_until_rescan_then_duplicate_is_ambiguous(self):
        self.journal('one.jsonl')
        with patch('quota_monitor.indexed.time.monotonic', return_value=0) as clock:
            source = indexed.DirectorySource(self.root)
            self.assertEqual(source.read('one')['selectedThreadId'], 'one')
            self.journal('second.jsonl')
            self.assertEqual(source.read('one')['summaries'], [])
            self.assertEqual(source.status, 'index_wait')
            clock.return_value = 31
            self.assertEqual(source.read('one')['summaries'], [])
            self.assertEqual(source.status, 'ambiguous')
            (self.root / 'second.jsonl').unlink()
            clock.return_value = 62
            self.assertEqual(source.read('one')['selectedThreadId'], 'one')

    def test_existing_file_identity_conflict_blocks_cached_match(self):
        self.journal('one.jsonl')
        other = self.journal('other.jsonl', 'two')
        source = indexed.DirectorySource(self.root)
        self.assertEqual(source.read('one')['selectedThreadId'], 'one')
        with other.open('a') as stream:
            stream.write('{"type":"session_meta","payload":{"id":"one"}}\n')
        self.assertEqual(source.read('one')['summaries'], [])
        self.assertEqual(source.status, 'incomplete')
        self.assertEqual(source.read('one')['summaries'], [])

    def test_byte_budget_is_global_and_progress_is_fair(self):
        self.journal('one.jsonl')
        self.journal('two.jsonl', 'two')
        source = indexed.DirectorySource(self.root, read_budget=64, max_files=4)
        for _ in range(30):
            payload = source.read('two')
            self.assertLessEqual(source.bytes_read, 64)
            if source.status == 'ok':
                break
        self.assertEqual(payload['selectedThreadId'], 'two')

    def test_limits_never_claim_complete_inventory(self):
        self.journal('nested/one.jsonl')
        self.journal('two.jsonl', 'two')
        for options in ({'max_entries': 1}, {'max_files': 1}, {'max_depth': 0}):
            source = indexed.DirectorySource(self.root, **options)
            self.assertEqual(source.read('one')['summaries'], [])
            self.assertEqual(source.status, 'incomplete')

    def test_corruption_and_partial_tail_remain_unknown(self):
        path = self.journal('one.jsonl')
        source = indexed.DirectorySource(self.root)
        self.assertEqual(source.read('one')['selectedThreadId'], 'one')
        with path.open('a') as stream:
            stream.write('{broken}\n')
        for _ in range(2):
            self.assertEqual(source.read('one')['summaries'], [])
            self.assertEqual(source.status, 'incomplete')
        path.write_text('{"type":"session_meta","payload":{"id":"one"}}\n')
        self.assertEqual(source.read('one')['selectedThreadId'], 'one')
        with path.open('a') as stream:
            stream.write('{"type":"session_meta"')
        self.assertEqual(source.read('one')['summaries'], [])

    def test_symlink_substitution_cannot_read_outside_root(self):
        path = self.journal('inside/one.jsonl')
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / 'one.jsonl'
            external.write_text('{"type":"session_meta","payload":{"id":"outside"}}\n')
            source = indexed.DirectorySource(self.root)
            self.assertEqual(source.read('one')['selectedThreadId'], 'one')
            path.unlink()
            path.parent.rmdir()
            path.parent.symlink_to(outside, target_is_directory=True)
            self.assertEqual(source.read('outside')['summaries'], [])
            from quota_monitor.journal import SessionJournal
            journal = SessionJournal('inside/one.jsonl', root=self.root)
            self.assertEqual(journal.poll()['status'], 'unavailable')

    def test_new_file_is_found_after_cooldown_without_filename_convention(self):
        with patch('quota_monitor.indexed.time.monotonic', return_value=0) as clock:
            source = indexed.DirectorySource(self.root)
            self.assertEqual(source.read('one')['summaries'], [])
            self.assertEqual(source.status, 'not_found')
            self.journal('random.jsonl')
            self.assertEqual(source.read('one')['summaries'], [])
            clock.return_value = 31
            self.assertEqual(source.read('one')['selectedThreadId'], 'one')

    def test_root_and_file_links_are_not_followed(self):
        from quota_monitor.journal import SessionJournal
        path = self.journal('one.jsonl')
        link = self.root / 'link.jsonl'
        link.symlink_to(path)
        self.assertEqual(SessionJournal('link.jsonl', root=self.root).poll()['status'], 'unavailable')
        root_link = self.root / 'root-link'
        root_link.symlink_to(self.root, target_is_directory=True)
        source = indexed.DirectorySource(root_link)
        self.assertEqual(source.read('one')['summaries'], [])
        self.assertEqual(source.status, 'unavailable')

    def test_unsupported_descriptor_scan_fails_closed(self):
        self.journal('one.jsonl')
        with patch('os.supports_fd', set()):
            source = indexed.DirectorySource(self.root)
            self.assertEqual(source.read('one')['summaries'], [])
            self.assertEqual(source.status, 'unavailable')
