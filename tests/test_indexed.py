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

    def test_named_hover_priority_includes_old_task_beyond_recent_window(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / 'rollout-date-active.jsonl'
            hover = root / 'rollout-date-hover.jsonl'
            self.write_rollout(active, 'active', 11)
            self.write_rollout(hover, 'hover', 77)
            os.utime(active, ns=(1, 1))
            os.utime(hover, ns=(2, 2))
            for index in range(140):
                key = 'task%03d' % index
                path = root / ('rollout-date-' + key + '.jsonl')
                self.write_rollout(path, key, index)
                os.utime(path, ns=(100 + index, 100 + index))
            source = NamedDirectorySource(root)
            source.prioritize('hover')
            payload = source.read('active')
            self.assertEqual(payload['selectedThreadId'], 'active')
            self.assertEqual(payload['sidebarStatus'],
                             {'threadId': 'hover', 'status': 'ready'})
            values = {item['thread_id']: item['latest_context_tokens']
                      for item in payload['summaries']}
            self.assertEqual(values['active'], 11)
            self.assertEqual(values['hover'], 77)
            self.assertIn(Path('rollout-date-hover.jsonl'), source._journals)
            self.assertLessEqual(len(source._journals), source.max_files)

    def test_named_hover_loading_omits_partial_context_and_uses_idle_active_budget(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / 'rollout-date-active.jsonl'
            hover = root / 'rollout-date-hover.jsonl'
            self.write_rollout(active, 'active', 11)
            source = NamedDirectorySource(root)
            self.assertEqual(source.read('active')['selectedThreadId'], 'active')
            self.write_rollout(hover, 'hover', 77, padding=400)
            source.read_budget = 256
            source.prioritize('hover')
            payload = source.read('active')
            self.assertEqual(payload['selectedThreadId'], 'active')
            self.assertEqual(payload['sidebarStatus']['threadId'], 'hover')
            self.assertEqual(payload['sidebarStatus']['status'], 'loading')
            self.assertLess(payload['sidebarStatus']['readBytes'],
                            payload['sidebarStatus']['totalBytes'])
            self.assertNotIn('hover', {item['thread_id'] for item in payload['summaries']})
            self.assertEqual(source._journals[Path('rollout-date-hover.jsonl')].reader.read_budget,
                             source.read_budget)
            self.assertEqual(source.bytes_read, source.read_budget)

    def test_named_ready_hover_is_published_while_large_active_log_is_still_loading(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = '01a08a0a-d922-7143-9a82-82451d38b81f'
            hover = '01a0d3fc-3dbf-7131-92f4-05e5f7514653'
            self.write_rollout(root / ('rollout-date-' + active + '.jsonl'), active, 11,
                               padding=750000)
            self.write_rollout(root / ('rollout-date-' + hover + '.jsonl'), hover, 77)
            source = NamedDirectorySource(root)
            source.read_budget = 2 * 1024 * 1024 + 8192
            source.prioritize(hover)
            payload = source.read(active)
            self.assertEqual(source.status, 'loading')
            self.assertIsNone(payload['selectedThreadId'])
            self.assertEqual(payload['sidebarStatus'],
                             {'threadId': hover, 'status': 'ready'})
            summary = next(item for item in payload['summaries']
                           if item['thread_id'] == hover)
            self.assertEqual(summary['latest_context_tokens'], 77)
            self.assertIn('local:' + hover, summary['thread_keys'])

    def test_named_pending_active_or_hover_never_republishes_stale_summary(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active_path = root / 'rollout-date-active.jsonl'
            hover_path = root / 'rollout-date-hover.jsonl'
            self.write_rollout(active_path, 'active', 80)
            self.write_rollout(hover_path, 'hover', 77)
            source = NamedDirectorySource(root)
            source.prioritize('hover')
            self.assertEqual(source.read('active')['sidebarStatus']['status'], 'ready')

            with active_path.open('a') as stream:
                stream.write('{"type":')
            active_pending = source.read('active')
            self.assertEqual(source.status, 'loading')
            self.assertIsNone(active_pending['selectedThreadId'])
            self.assertEqual(active_pending['sidebarStatus'],
                             {'threadId': 'hover', 'status': 'ready'})
            self.assertEqual({item['thread_id'] for item in active_pending['summaries']},
                             {'hover'})

            active_path.write_text(active_path.read_text() + '}\n')
            source.read('active')
            with hover_path.open('a') as stream:
                stream.write('{"type":')
            hover_pending = source.read('active')
            self.assertEqual(hover_pending['sidebarStatus'],
                             {'threadId': 'hover', 'status': 'loading'})
            self.assertNotIn('hover', {item['thread_id']
                                       for item in hover_pending['summaries']})

    def test_named_pending_duplicate_suffix_blocks_complete_hover_summary(self):
        from quota_monitor.indexed import NamedDirectorySource
        for pending_prefix in (
                json.dumps({'type': 'session_meta', 'payload': {'id': 'hover'}}) + '\n',
                ''):
            with self.subTest(identity_known=bool(pending_prefix)), \
                    tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.write_rollout(root / 'rollout-date-active.jsonl', 'active', 11)
                self.write_rollout(root / 'rollout-a-hover.jsonl', 'hover', 77)
                (root / 'rollout-b-hover.jsonl').write_text(pending_prefix + '{"type":')
                source = NamedDirectorySource(root)
                source.prioritize('hover')
                payload = source.read('active')
                self.assertEqual(payload['sidebarStatus'],
                                 {'threadId': 'hover', 'status': 'loading'})
                self.assertNotIn('hover', {item['thread_id']
                                           for item in payload['summaries']})

    def test_named_hover_loading_reports_bounded_byte_progress(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_rollout(root / 'rollout-date-active.jsonl', 'active', 11)
            self.write_rollout(root / 'rollout-date-hover.jsonl', 'hover', 77,
                               padding=1500000)
            source = NamedDirectorySource(root)
            source.prioritize('hover')
            payload = source.read('active')
            status = payload['sidebarStatus']
            self.assertEqual(status['threadId'], 'hover')
            self.assertEqual(status['status'], 'loading')
            self.assertGreater(status['readBytes'], 0)
            self.assertLess(status['readBytes'], status['totalBytes'])
            self.assertEqual(status['totalBytes'],
                             (root / 'rollout-date-hover.jsonl').stat().st_size)

    def test_named_inventory_wait_withholds_hover_until_uniqueness_is_rescanned(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory, \
                patch('quota_monitor.indexed.time.monotonic', return_value=0) as clock:
            root = Path(directory)
            self.write_rollout(root / 'rollout-date-active.jsonl', 'active', 11)
            self.write_rollout(root / 'rollout-date-hover.jsonl', 'hover', 77)
            source = NamedDirectorySource(root)
            source.prioritize('hover')
            self.assertEqual(source.read('active')['sidebarStatus']['status'], 'ready')

            self.write_rollout(root / 'rollout-copy-hover.jsonl', 'hover', 88)
            payload = source.read('active')
            self.assertEqual(source.status, 'index_wait')
            self.assertEqual(payload['sidebarStatus'],
                             {'threadId': 'hover', 'status': 'index_wait'})
            self.assertEqual(payload['summaries'], [])
            clock.return_value = 31
            rescanned = source.read('active')
            self.assertEqual(rescanned['sidebarStatus']['status'], 'ambiguous')
            self.assertNotIn('hover', {item['thread_id'] for item in rescanned['summaries']})

            source.prioritize('missing')
            self.assertEqual(source.read('active')['sidebarStatus']['status'], 'not_found')
            self.write_rollout(root / 'rollout-date-missing.jsonl', 'missing', 33)
            waiting = source.read('active')
            self.assertEqual(source.status, 'index_wait')
            self.assertEqual(waiting['sidebarStatus'],
                             {'threadId': 'missing', 'status': 'index_wait'})

    def test_named_completed_priority_and_active_transfer_budget_to_background(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / 'rollout-date-active.jsonl'
            hover = root / 'rollout-date-hover.jsonl'
            background = root / 'rollout-date-background.jsonl'
            self.write_rollout(active, 'active', 11)
            source = NamedDirectorySource(root)
            self.assertEqual(source.read('active')['selectedThreadId'], 'active')
            self.write_rollout(hover, 'hover', 22)
            self.write_rollout(background, 'background', 33, padding=400)
            source.read_budget = 512
            source.prioritize('hover')
            payload = source.read('active')
            self.assertEqual(payload['sidebarStatus']['status'], 'ready')
            background_reader = source._journals[Path('rollout-date-background.jsonl')].reader
            self.assertGreater(background_reader._offset, 256)
            self.assertLessEqual(source.bytes_read, source.read_budget)

    def test_named_duplicate_hover_identity_is_ambiguous_without_replacing_active(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_rollout(root / 'rollout-date-active.jsonl', 'active', 11)
            for prefix in ('a', 'b'):
                self.write_rollout(root / ('rollout-' + prefix + '-hover.jsonl'), 'hover', 90)
            source = NamedDirectorySource(root)
            source.prioritize('hover')
            payload = source.read('active')
            self.assertEqual(payload['selectedThreadId'], 'active')
            self.assertEqual(payload['sidebarStatus'],
                             {'threadId': 'hover', 'status': 'ambiguous'})
            self.assertEqual(next(item for item in payload['summaries']
                                  if item['thread_id'] == 'active')['latest_context_tokens'], 11)
            self.assertNotIn('hover', {item['thread_id'] for item in payload['summaries']})

    def test_named_priority_can_be_cleared_and_rejects_invalid_keys(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_rollout(root / 'rollout-date-active.jsonl', 'active', 11)
            source = NamedDirectorySource(root)
            source.prioritize('missing')
            payload = source.read('active')
            self.assertEqual(payload['sidebarStatus'],
                             {'threadId': 'missing', 'status': 'not_found'})
            source.prioritize(None)
            self.assertNotIn('sidebarStatus', source.read('active'))
            with self.assertRaises(ValueError):
                source.prioritize('bad/key')

    def test_named_first_hover_reuses_completed_background_journal(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_rollout(root / 'rollout-date-active.jsonl', 'active', 11)
            self.write_rollout(root / 'rollout-date-hover.jsonl', 'hover', 77)
            source = NamedDirectorySource(root)
            self.assertEqual(source.read('active')['selectedThreadId'], 'active')
            source.prioritize('hover')
            payload = source.read('active')
            self.assertEqual(source.bytes_read, 0)
            self.assertEqual(payload['sidebarStatus'],
                             {'threadId': 'hover', 'status': 'ready'})
            self.assertEqual(next(item for item in payload['summaries']
                                  if item['thread_id'] == 'hover')['latest_context_tokens'], 77)

    def test_named_discarded_long_body_does_not_hide_complete_hover_numbers(self):
        from quota_monitor.indexed import NamedDirectorySource
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_rollout(root / 'rollout-date-active.jsonl', 'active', 11)
            hover = root / 'rollout-date-hover.jsonl'
            rows = [
                {'type': 'session_meta', 'payload': {'id': 'hover'}},
                {'type': 'response_item', 'payload': {'body': 'x' * 300}},
                {'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {
                    'last_token_usage': {'input_tokens': 77},
                    'model_context_window': 100}}},
            ]
            hover.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            source = NamedDirectorySource(root)
            source.line_limit = 200
            source.prioritize('hover')
            payload = source.read('active')
            self.assertEqual(payload['sidebarStatus'],
                             {'threadId': 'hover', 'status': 'ready'})
            self.assertEqual(next(item for item in payload['summaries']
                                  if item['thread_id'] == 'hover')['latest_context_tokens'], 77)
