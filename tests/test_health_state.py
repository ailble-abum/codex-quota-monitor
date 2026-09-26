import unittest

from quota_monitor.health_state import HealthState


def compacted():
    return {'type': 'compacted', 'timestamp': '2026-09-21T00:00:00Z', 'payload': {}}


def tokens(value, window=200, cached=None, total=None):
    last = {'input_tokens': value, 'total_tokens': value + 1}
    if cached is not None:
        last['cached_input_tokens'] = cached
    return {'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {
        'last_token_usage': last,
        'total_token_usage': {'total_tokens': value + 1 if total is None else total},
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

    def test_zero_accounting_record_is_not_the_first_post_compaction_request(self):
        state = HealthState()
        state.accept(tokens(180, total=500))
        state.accept(compacted())
        placeholder = tokens(0, total=500)
        placeholder['payload']['info']['last_token_usage']['total_tokens'] = 30
        state.accept(placeholder)
        self.assertIsNone(state.snapshot()['after'])
        state.accept(tokens(80, cached=60, total=581))
        result = state.snapshot()
        self.assertEqual(result['after'], 80)
        self.assertEqual(result['afterPercent'], 40)

    def test_zero_then_replayed_old_snapshot_keeps_waiting_for_new_request(self):
        state = HealthState()
        old = tokens(180, total=500)
        state.accept(old)
        state.accept(compacted())
        state.accept(tokens(0, total=500))
        state.accept(old)
        self.assertIsNone(state.snapshot()['after'])
        state.accept(tokens(75, total=576))
        self.assertEqual(state.snapshot()['after'], 75)

    def test_cached_input_is_a_breakdown_not_added_to_context_input(self):
        state = HealthState()
        state.accept(compacted())
        state.accept(tokens(100, window=200, cached=80, total=101))
        result = state.snapshot()
        self.assertEqual(result['after'], 100)
        self.assertEqual(result['afterPercent'], 50)

    def test_missing_input_keeps_waiting_for_a_measured_request(self):
        state = HealthState()
        state.accept(compacted())
        unknown = tokens(0)
        del unknown['payload']['info']['last_token_usage']['input_tokens']
        state.accept(unknown)
        self.assertIsNone(state.snapshot()['after'])
        state.accept(tokens(50))
        self.assertEqual(state.snapshot()['after'], 50)

    def test_reset_drops_compaction_state(self):
        state = HealthState()
        state.accept(compacted())
        state.reset()
        self.assertEqual(state.snapshot()['count'], 0)
        self.assertIsNone(state.snapshot()['after'])


if __name__ == '__main__':
    unittest.main()
