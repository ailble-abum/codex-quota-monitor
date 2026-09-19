import unittest

from quota_monitor.session import SessionState


def event(total=100, latest=20, window=200):
    return {'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {
        'total_token_usage': {'total_tokens': total},
        'last_token_usage': {'input_tokens': latest},
        'model_context_window': window}}}


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.state = SessionState()

    def test_empty_is_unknown(self):
        snapshot = self.state.snapshot()
        self.assertIsNone(snapshot['context_percent'])
        self.assertIsNone(snapshot['total']['total_tokens'])

    def test_token_events_are_snapshots_not_increments(self):
        self.state.accept(event())
        self.state.accept(event())
        snapshot = self.state.snapshot()
        self.assertEqual(snapshot['total']['total_tokens'], 100)
        self.assertEqual(snapshot['context_percent'], 10)
        self.assertEqual(snapshot['counter_resets'], 0)

    def test_missing_fields_replace_old_values_with_unknown(self):
        self.state.accept(event())
        self.state.accept(event(None, None, None))
        snapshot = self.state.snapshot()
        self.assertIsNone(snapshot['context_percent'])
        self.assertIsNone(snapshot['window'])
        self.assertIsNone(snapshot['total']['total_tokens'])

    def test_invalid_counts_are_unknown(self):
        for value in (True, -1, 2.5, '20', float('inf'), 2**63):
            self.state.accept(event(value, value, value))
            snapshot = self.state.snapshot()
            self.assertIsNone(snapshot['context_percent'])
            self.assertIsNone(snapshot['total']['total_tokens'])

    def test_zero_is_valid_but_zero_window_is_unknown(self):
        self.state.accept(event(0, 0, 0))
        snapshot = self.state.snapshot()
        self.assertEqual(snapshot['total']['total_tokens'], 0)
        self.assertIsNone(snapshot['context_percent'])

    def test_total_rollback_is_reported_and_latest_snapshot_wins(self):
        self.state.accept(event(100))
        self.state.accept(event(50))
        self.state.accept(event(50))
        self.assertEqual(self.state.snapshot()['counter_resets'], 1)
        self.assertEqual(self.state.snapshot()['total']['total_tokens'], 50)

    def test_model_change_clears_context_until_new_usage(self):
        self.state.accept({'type': 'turn_context', 'payload': {'model': 'alpha', 'effort': 'high'}})
        self.state.accept(event())
        self.state.accept({'type': 'turn_context', 'payload': {'model': 'beta'}})
        snapshot = self.state.snapshot()
        self.assertEqual(snapshot['model'], 'beta')
        self.assertIsNone(snapshot['effort'])
        self.assertIsNone(snapshot['context_percent'])
        self.assertEqual(snapshot['total']['total_tokens'], 100)

    def test_rate_limit_only_event_preserves_usage_without_inventing_quota(self):
        self.state.accept(event())
        self.state.accept({'type': 'event_msg', 'payload': {'type': 'token_count', 'info': None, 'rate_limits': {'secret': 'hidden'}}})
        self.assertEqual(self.state.snapshot()['total']['total_tokens'], 100)
        self.assertNotIn('rate_limits', self.state.snapshot())

    def test_compaction_clears_context_and_never_exports_summary(self):
        self.state.accept(event())
        self.state.accept({'type': 'compacted', 'payload': {'message': 'private summary'}})
        snapshot = self.state.snapshot()
        self.assertEqual(snapshot['compactions'], 1)
        self.assertIsNone(snapshot['context_percent'])
        self.assertNotIn('private', repr(snapshot))
        self.state.accept(event(110, 5, 200))
        self.assertEqual(self.state.snapshot()['context_percent'], 2.5)

    def test_unknown_and_malformed_events_are_ignored(self):
        original = self.state.snapshot()
        for item in (None, [], {'type': 'event_msg', 'payload': []}, {'type': 'turn_context', 'payload': None}, {'type': 'response_item', 'payload': {'text': 'private'}}):
            self.state.accept(item)
        self.assertEqual(self.state.snapshot(), original)

    def test_snapshot_is_detached(self):
        self.state.accept(event())
        copy = self.state.snapshot()
        copy['total']['total_tokens'] = 999
        self.assertEqual(self.state.snapshot()['total']['total_tokens'], 100)

    def test_cached_and_reasoning_fields_are_not_added_to_totals(self):
        row = event(100)
        row['payload']['info']['last_token_usage'].update({
            'cached_input_tokens': 15, 'output_tokens': 10,
            'reasoning_output_tokens': 4, 'total_tokens': 30})
        self.state.accept(row)
        snapshot = self.state.snapshot()
        self.assertEqual(snapshot['last']['total_tokens'], 30)
        self.assertEqual(snapshot['context_percent'], 10)


if __name__ == '__main__':
    unittest.main()
