import json
import tempfile
import unittest
from pathlib import Path

from quota_monitor.local_samples import LocalSampleStore


class HistoryStoreTests(unittest.TestCase):
    def test_history_is_opt_in_and_numeric_only(self):
        with tempfile.TemporaryDirectory() as directory:
            now = [1000.0]
            store = LocalSampleStore(directory, clock=lambda: now[0])
            result = store.record(
                {'windows': [{'key': 'primary', 'remaining': 75, 'secret': 'drop'}]},
                {'latest_context_percent': 40, 'latest_turn_input_tokens': 100,
                 'latest_turn_cached_input_tokens': 25, 'path': '/private'},
                {'count': 2, 'events': ['drop']}, 'gpt-5.6-luna')
            self.assertEqual(result['samples'], 1)
            saved = json.loads(Path(directory, 'history.json').read_text())
            self.assertNotIn('secret', repr(saved))
            self.assertNotIn('/private', repr(saved))
            self.assertEqual(saved[0]['windows'][0], {'key': 'primary', 'remaining': 75})

    def test_writes_are_throttled_and_old_rows_expire(self):
        with tempfile.TemporaryDirectory() as directory:
            now = [1000.0]
            store = LocalSampleStore(directory, retention=60, clock=lambda: now[0])
            store.record({'windows': []}, {}, {}, None)
            now[0] += 10
            store.record({'windows': [{'key': 'primary', 'remaining': 20}]}, {}, {}, None)
            self.assertEqual(store.summary()['samples'], 1)
            now[0] += 61
            store.record({'windows': [{'key': 'primary', 'remaining': 10}]}, {}, {}, None)
            self.assertEqual(store.summary()['samples'], 1)
            self.assertEqual(store.summary()['minRemaining'], 10)

    def test_enrich_quota_derives_pace_without_using_reset_as_exhaustion(self):
        with tempfile.TemporaryDirectory() as directory:
            now = [2000.0]
            store = LocalSampleStore(directory, clock=lambda: now[0])
            quota = {'windows': [{'key': 'primary', 'remaining': 50, 'duration': 300,
                                  'resetsAt': 2300}]}
            store.record({'windows': [{'key': 'primary', 'remaining': 80}]}, {}, {}, None)
            now[0] += 100
            store.record({'windows': [{'key': 'primary', 'remaining': 50}]}, {}, {}, None)
            result = store.enrich_quota(quota, now=now[0])
            self.assertEqual(result['budget']['kind'], 'exhaust')
            self.assertGreater(result['windows'][0]['exhaustInSec'], 0)
            self.assertIn('paceDelta', result['windows'][0])


if __name__ == '__main__':
    unittest.main()
