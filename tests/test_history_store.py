import json
import tempfile
import unittest
from pathlib import Path

from quota_monitor.local_samples import LocalSampleStore


class HistoryStoreTests(unittest.TestCase):
    def test_weekly_report_is_account_scoped_and_counts_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            now = [7 * 86400 + 1000.0]
            store = LocalSampleStore(directory, clock=lambda: now[0])
            one = {'accountKey': 'a' * 64, 'windows': []}
            two = {'accountKey': 'b' * 64, 'windows': []}
            store.record(one, {'latest_context_percent': 20}, {}, 'model-one')
            now[0] += 60
            store.record(two, {'latest_context_percent': 99}, {}, 'model-two')
            now[0] += 86400
            report = store.record(one, {'latest_context_percent': 80}, {}, 'model-one')['weekly']
            self.assertEqual(report['timezone'], 'UTC')
            self.assertEqual(len(report['days']), 7)
            self.assertEqual(sum(day['samples'] for day in report['days']), 2)
            self.assertEqual(report['modelCounts'], [{'model': 'model-one', 'samples': 2}])
            self.assertEqual(report['days'][-1]['peakContext'], 80)
            store.rows.append({'at': now[0], 'accountKey': 'a' * 64, 'model': {'bad': 'row'}})
            self.assertEqual(store.summary('a' * 64)['weekly']['modelCounts'],
                             [{'model': 'model-one', 'samples': 2}])

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
            quota = {'accountKey': 'a' * 64, 'windows': [{'key': 'primary', 'remaining': 50, 'duration': 300,
                                  'resetsAt': 2300}]}
            store.record({'accountKey': 'a' * 64, 'windows': [{'key': 'primary', 'remaining': 80}]}, {}, {}, None)
            now[0] += 100
            store.record({'accountKey': 'a' * 64, 'windows': [{'key': 'primary', 'remaining': 50}]}, {}, {}, None)
            result = store.enrich_quota(quota, now=now[0])
            self.assertEqual(result['budget']['kind'], 'exhaust')
            self.assertGreater(result['windows'][0]['exhaustInSec'], 0)
            self.assertIn('paceDelta', result['windows'][0])

    def test_account_switch_does_not_mix_history_or_pace(self):
        with tempfile.TemporaryDirectory() as directory:
            now = [2000.0]
            store = LocalSampleStore(directory, clock=lambda: now[0])
            one = {'accountKey': 'a' * 64, 'windows': [{'key': 'primary', 'remaining': 80}]}
            two = {'accountKey': 'b' * 64, 'windows': [{'key': 'primary', 'remaining': 50}]}
            store.record(one, {'latest_context_percent': 90}, {}, 'first-model')
            now[0] += 60
            summary = store.record(two, {'latest_context_percent': 20}, {}, 'second-model')
            self.assertEqual(summary['samples'], 1)
            self.assertEqual(summary['models'], ['second-model'])
            self.assertEqual(summary['peakContext'], 20)
            self.assertNotIn('exhaustInSec', store.enrich_quota(two)['windows'][0])
            now[0] += 60
            two['windows'][0]['remaining'] = 40
            store.record(two, {}, {}, None)
            self.assertIn('exhaustInSec', store.enrich_quota(two)['windows'][0])
            self.assertEqual(store.summary('a' * 64)['samples'], 1)


if __name__ == '__main__':
    unittest.main()
