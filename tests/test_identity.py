import json
import tempfile
import unittest
from pathlib import Path

from quota_monitor.journal import SessionJournal


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'misleading-filename.jsonl'
        self.path.touch()

    def append_meta(self, value):
        with self.path.open('a') as stream:
            stream.write(json.dumps({'type': 'session_meta', 'payload': value}) + '\n')

    def test_metadata_identity_and_duplicate(self):
        self.append_meta({'id': 'demo', 'cwd': 'SECRET', 'session_id': 'root',
                          'parent_thread_id': 'parent', 'forked_from_id': 'source'})
        journal = SessionJournal(self.path)
        first = journal.poll()
        self.assertEqual(first.get('thread_id'), 'demo')
        self.assertEqual(first.get('identity_status'), 'verified')
        self.assertNotIn('SECRET', str(first))
        self.append_meta({'id': 'demo'})
        self.assertEqual(journal.poll().get('identity_status'), 'verified')

    def test_missing_and_late_metadata(self):
        journal = SessionJournal(self.path)
        self.assertEqual(journal.poll().get('identity_status'), 'missing')
        self.append_meta({'id': 'demo'})
        self.assertEqual(journal.poll().get('thread_id'), 'demo')

    def test_conflict_is_sticky(self):
        self.append_meta({'id': 'demo'})
        journal = SessionJournal(self.path)
        journal.poll()
        self.append_meta({'id': 'other'})
        self.assertEqual(journal.poll().get('identity_status'), 'conflict')
        self.append_meta({'id': 'demo'})
        result = journal.poll()
        self.assertEqual(result.get('identity_status'), 'conflict')
        self.assertIsNone(result.get('thread_id'))

    def test_invalid_metadata_cannot_be_repaired_by_append(self):
        for value in (None, {}, {'id': 42}, {'id': 'local:demo'}, {'id': '../demo'}):
            with self.subTest(value=value):
                self.path.write_text('')
                self.append_meta(value)
                self.append_meta({'id': 'demo'})
                result = SessionJournal(self.path).poll()
                self.assertEqual(result.get('identity_status'), 'conflict')
                self.assertIsNone(result.get('thread_id'))

    def test_replacement_discards_prior_identity(self):
        self.append_meta({'id': 'demo'})
        journal = SessionJournal(self.path)
        journal.poll()
        replacement = self.path.with_suffix('.new')
        replacement.write_text('{}\n')
        replacement.replace(self.path)
        result = journal.poll()
        self.assertTrue(result['reset'])
        self.assertEqual(result.get('identity_status'), 'missing')
        self.assertIsNone(result.get('thread_id'))

    def test_split_metadata_waits_for_complete_line(self):
        self.append_meta({'id': 'demo'})
        journal = SessionJournal(self.path, read_budget=10)
        result = journal.poll()
        self.assertEqual(result.get('identity_status'), 'missing')
        while result['more']:
            result = journal.poll()
        self.assertEqual(result.get('thread_id'), 'demo')
