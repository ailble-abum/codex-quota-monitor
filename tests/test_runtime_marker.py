import json
from pathlib import Path
import tempfile
import unittest

from quota_monitor.runtime_marker import StatusStore


class StatusSnapshotTests(unittest.TestCase):
    def test_status_is_private_fresh_and_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            now = [1000.0]
            store = StatusStore(directory, clock=lambda: now[0])
            self.assertEqual(store.read(), 'missing')
            store.write('updated')
            path = Path(directory, 'status.json')
            self.assertEqual(store.read(), 'updated')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(path.read_text()), {'status': 'updated', 'updatedAt': 1000})
            now[0] += 130
            self.assertEqual(store.read(), 'stale')
            store.write('not_found')
            self.assertEqual(store.read(), 'not_found')
            with self.assertRaises(ValueError):
                store.write('secret/path')
            path.write_text('x' * 513)
            self.assertEqual(store.read(), 'invalid')
