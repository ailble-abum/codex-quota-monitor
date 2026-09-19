import unittest
import time

from quota_monitor.compat import panel_payload, panel_summary


def reading(status='ok', more=False):
    return {'status': status, 'more': more, 'identity_status': 'verified',
            'thread_id': 'one', 'session': {
        'model': 'demo', 'effort': 'high', 'window': 1000,
        'context_percent': 10.0,
        'last': {'input_tokens': 100, 'cached_input_tokens': 80,
                 'output_tokens': 20, 'reasoning_output_tokens': 5, 'total_tokens': 120},
        'total': {'input_tokens': 500, 'cached_input_tokens': 400,
                  'output_tokens': 100, 'reasoning_output_tokens': 25, 'total_tokens': 600}}}


class CompatibilityTests(unittest.TestCase):
    def test_payload_carries_generation_time_for_consumer_expiry(self):
        before = time.time()
        payload = panel_payload({'one': reading()}, 'one')
        after = time.time()
        self.assertIsInstance(payload.get('observedAt'), (int, float))
        self.assertLessEqual(before, payload['observedAt'])
        self.assertLessEqual(payload['observedAt'], after)

    def test_identity_cannot_be_bypassed_by_mapping_key(self):
        for changes in ({'thread_id': 'two'}, {'identity_status': 'missing'},
                        {'identity_status': 'conflict'}, {'identity_status': None}):
            result = reading()
            result.update(changes)
            with self.subTest(changes=changes):
                self.assertEqual(panel_payload({'one': result}, 'one')['summaries'], [])

    def test_projection_preserves_metric_meanings(self):
        summary = panel_summary('local:one', reading())
        self.assertEqual(summary['thread_id'], 'one')
        self.assertEqual(summary['thread_keys'], ['one', 'local:one'])
        self.assertEqual(summary['latest_context_tokens'], 100)
        self.assertEqual(summary['latest_context_percent'], 10.0)
        self.assertEqual(summary['latest_turn_total_tokens'], 120)
        self.assertEqual(summary['session_total_tokens'], 600)
        self.assertEqual(summary['latest_turn_cached_input_tokens'], 80)
        self.assertEqual(summary['session_reasoning_tokens'], 25)
        self.assertEqual(summary['reasoning_effort'], 'high')

    def test_unknown_is_not_zero(self):
        result = reading()
        result['session']['last'] = {}
        result['session']['total'] = {}
        summary = panel_summary('one', result)
        self.assertIsNone(summary['latest_turn_total_tokens'])
        self.assertIsNone(summary['session_total_tokens'])

    def test_partial_and_unavailable_are_not_published(self):
        for result in (reading('unavailable'), reading(more=True)):
            self.assertIsNone(panel_summary('one', result))

    def test_active_task_never_falls_back_to_another_task(self):
        payload = panel_payload({'one': reading()}, 'two')
        self.assertEqual(payload['activeThreadId'], 'two')
        self.assertIsNone(payload['selectedThreadId'])
        self.assertEqual(payload['summaries'], [])

    def test_selected_alias_is_resolved(self):
        payload = panel_payload({'one': reading()}, 'local:one')
        self.assertEqual(payload['selectedThreadId'], 'one')
        self.assertEqual(len(payload['summaries']), 1)
        self.assertEqual(payload['detailsByThread'], {})
        self.assertIsNone(payload['detail'])

    def test_absent_active_task_is_not_inferred(self):
        self.assertEqual(panel_payload({'one': reading()}, None)['summaries'], [])

    def test_metadata_not_in_allowlist_is_removed(self):
        result = reading()
        result['session'].update({'cwd': '/private/project', 'text': 'secret'})
        summary = panel_summary('one', result)
        self.assertNotIn('cwd', summary)
        self.assertNotIn('secret', repr(summary))
        self.assertNotIn('/private', repr(summary))

    def test_zero_totals_remain_visible(self):
        result = reading()
        result['session']['total']['total_tokens'] = 0
        payload = panel_payload({'one': result}, 'one')
        self.assertEqual(payload['summaries'][0]['session_total_tokens'], 0)


if __name__ == '__main__':
    unittest.main()
