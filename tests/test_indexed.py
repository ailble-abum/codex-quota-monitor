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

class NamedDirectoryTests(unittest.TestCase):
    @staticmethod
    def write_rollout(path, key, count, padding=0):
        rows = [
            {'type': 'session_meta', 'payload': {'id': key}},
            {'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {
                'last_token_usage': {'input_tokens': count}, 'model_context_window': 100}}},
        ]
        text = ''.join(json.dumps(row) + '\n' for row in rows)
        if padding:
            text += ('{}\n' * padding)
        path.write_text(text)

    def test_named_source_projects_verified_summaries_for_sidebar(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for key, count in (('one', 10), ('two', 20)):
                path = root / ('rollout-date-' + key + '.jsonl')
                path.write_text(''.join(json.dumps(row) + '\n' for row in [
                    {'type': 'session_meta', 'payload': {'id': key}},
                    {'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {
                        'last_token_usage': {'input_tokens': count}, 'model_context_window': 100}}}]))
            payload = NamedDirectorySource(root).read('one')
            self.assertEqual(payload['selectedThreadId'], 'one')
            self.assertEqual({item['thread_id'] for item in payload['summaries']}, {'one', 'two'})

    def test_named_accepts_uuid_with_numeric_final_group_but_rejects_short_numeric_noise(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = '01a08a0a-d922-7143-9a82-123456789012'
            self.write_rollout(root / ('rollout-date-' + key + '.jsonl'), key, 42)
            (root / 'rollout-other-123.jsonl').write_text('broken\n')
            source = NamedDirectorySource(root)
            payload = source.read(key)
            self.assertEqual(payload['selectedThreadId'], key)
            self.assertEqual(payload['summaries'][0]['latest_context_tokens'], 42)
            self.assertEqual(list(source._journals), [Path('rollout-date-' + key + '.jsonl')])

    def test_named_rollout_accepts_bounded_compacted_record(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            selected = root / 'rollout-date-one.jsonl'
            compacted = json.dumps({'type': 'compacted', 'payload': {'blob': 'x' * 1100000}})
            selected.write_text(compacted + '\n' +
                                json.dumps({'type': 'session_meta', 'payload': {'id': 'one'}}) + '\n')
            source = NamedDirectorySource(root)
            self.assertEqual(source.read('one')['selectedThreadId'], 'one')
            self.assertEqual(source.status, 'ok')

    def test_named_lookup_ignores_unrelated_large_or_broken_logs(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(140):
                (root / ('rollout-other-%s.jsonl' % index)).write_text('broken\n')
            selected = root / 'rollout-date-one.jsonl'
            selected.write_text(json.dumps({'type':'session_meta','payload':{'id':'one'}})+'\n')
            source = NamedDirectorySource(root)
            self.assertEqual(source.read('one')['selectedThreadId'], 'one')
            self.assertLess(source.bytes_read, 1024)
            self.assertIsNone(source.read('missing')['selectedThreadId'])
            self.assertEqual(source.status, 'not_found')
            selected.write_text(json.dumps({'type':'session_meta','payload':{'id':'wrong'}})+'\n')
            self.assertIsNone(source.read('one')['selectedThreadId'])

    def test_named_duplicate_identity_is_not_selected(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for prefix in ('a', 'b'):
                (root / ('rollout-%s-one.jsonl' % prefix)).write_text(json.dumps({'type':'session_meta','payload':{'id':'one'}})+'\n')
            source = NamedDirectorySource(root)
            self.assertIsNone(source.read('one')['selectedThreadId'])
            self.assertEqual(source.status, 'ambiguous')

    def test_named_duplicate_selected_reads_share_global_budget(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for prefix in ('a', 'b', 'c'):
                self.write_rollout(root / ('rollout-%s-one.jsonl' % prefix), 'one', 10,
                                   padding=200)
            source = NamedDirectorySource(root)
            source.read_budget = 512
            self.assertIsNone(source.read('one')['selectedThreadId'])
            self.assertEqual(source.status, 'ambiguous')
            self.assertLessEqual(source.bytes_read, source.read_budget)

    def test_named_switch_waits_for_complete_selected_log_and_reuses_cursor(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            one = root / 'rollout-date-one.jsonl'
            two = root / 'rollout-date-two.jsonl'
            self.write_rollout(one, 'one', 10)
            self.write_rollout(two, 'two', 20, padding=200)
            with two.open('a') as stream:
                stream.write(json.dumps({'type': 'event_msg', 'payload': {'type': 'token_count',
                    'info': {'last_token_usage': {'input_tokens': 90},
                             'model_context_window': 100}}}) + '\n')
            source = NamedDirectorySource(root)
            source.read_budget = 256
            self.assertEqual(source.read('one')['summaries'][0]['latest_context_tokens'], 10)
            self.assertEqual(source.read('two')['summaries'], [])
            self.assertEqual(source.status, 'loading')
            while source.status == 'loading':
                payload = source.read('two')
            self.assertEqual(payload['summaries'][0]['latest_context_tokens'], 90)
            source.read_budget = 4 * 1024 * 1024
            with one.open('a') as stream:
                stream.write(json.dumps({'type': 'event_msg', 'payload': {'type': 'token_count',
                    'info': {'last_token_usage': {'input_tokens': 40},
                             'model_context_window': 100}}}) + '\n')
            self.assertEqual(source.read('two')['summaries'][0]['latest_context_tokens'], 90)
            self.assertEqual(source.read('one')['summaries'][0]['latest_context_tokens'], 40)
            self.assertEqual(source.bytes_read, 0)

    def test_named_same_size_head_rewrite_invalidates_cached_identity(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            selected = root / 'rollout-date-one.jsonl'
            other = root / 'rollout-date-two.jsonl'
            self.write_rollout(selected, 'one', 10)
            self.write_rollout(other, 'two', 20)
            source = NamedDirectorySource(root)
            self.assertEqual(source.read('one')['selectedThreadId'], 'one')
            self.assertEqual(source.read('two')['selectedThreadId'], 'two')
            before = selected.read_text()
            selected.write_text(before.replace('"id": "one"', '"id": "bad"', 1))
            self.assertEqual(selected.stat().st_size, len(before.encode()))
            self.assertIsNone(source.read('one')['selectedThreadId'])

    def test_named_requires_filename_and_content_identity_in_small_and_large_inventory(self):
        from quota_monitor.indexed import NamedDirectorySource
        for filler_count in (0, 140):
            with self.subTest(filler_count=filler_count), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                selected = root / 'rollout-date-target.jsonl'
                impostor = root / 'rollout-date-other.jsonl'
                self.write_rollout(selected, 'target', 77)
                self.write_rollout(impostor, 'target', 99)
                os.utime(selected, ns=(1, 1))
                for index in range(filler_count):
                    key = 'task%03d' % index
                    self.write_rollout(root / ('rollout-date-' + key + '.jsonl'), key, index)
                payload = NamedDirectorySource(root).read('target')
                self.assertEqual(payload['selectedThreadId'], 'target')
                target_rows = [item for item in payload['summaries'] if item['thread_id'] == 'target']
                self.assertEqual([item['latest_context_tokens'] for item in target_rows], [77])

    def test_named_inventory_prioritizes_selected_with_bounded_recent_window(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            selected = root / 'rollout-date-target.jsonl'
            self.write_rollout(selected, 'target', 77)
            os.utime(selected, ns=(1, 1))
            for index in range(140):
                key = 'task%03d' % index
                self.write_rollout(root / ('rollout-date-' + key + '.jsonl'), key, index)
            source = NamedDirectorySource(root)
            payload = source.read('target')
            self.assertEqual(payload['selectedThreadId'], 'target')
            self.assertEqual(next(item for item in payload['summaries']
                                  if item['thread_id'] == 'target')['latest_context_tokens'], 77)
            self.assertLessEqual(len(source._journals), source.max_files)
            self.assertEqual(len(source._journals), 128)
