import unittest

from quota_monitor.health_state import HealthState


def compacted():
    return {'type': 'compacted', 'timestamp': '2026-09-21T00:00:00Z', 'payload': {}}


def tokens(value, window=200):
    return {'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {
        'last_token_usage': {'input_tokens': value, 'total_tokens': value + 1},
        'total_token_usage': {'total_tokens': value + 1},
        'model_context_window': window}}}


class HealthStateTests(unittest.TestCase):
    def test_compaction_records_first_following_request_and_recommendation(self):
        state = HealthState()
        state.accept(tokens(20))
        state.accept(compacted())
        state.accept(tokens(100))
        result = state.snapshot()
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['after'], 100)
        self.assertEqual(result['afterPercent'], 50)
        self.assertTrue(result['recommendHandoff'])
        self.assertEqual(result['reason'], 'baseline')

    def test_duplicate_token_snapshots_do_not_inflate_request_intervals(self):
        state = HealthState()
        state.accept(tokens(20))
        state.accept(compacted())
        state.accept(tokens(40))
        state.accept(tokens(40))
        state.accept(compacted())
        state.accept(tokens(50))
        state.accept(compacted())
        state.accept(tokens(60))
        result = state.snapshot()
        self.assertEqual(result['count'], 3)
        self.assertEqual(result['intervals'], [1, 1])
        self.assertTrue(result['recommendHandoff'])
        self.assertEqual(result['reason'], 'frequency')

    def test_reset_drops_compaction_state(self):
        state = HealthState()
        state.accept(compacted())
        state.reset()
        self.assertEqual(state.snapshot()['count'], 0)
        self.assertIsNone(state.snapshot()['after'])


if __name__ == '__main__':
    unittest.main()
